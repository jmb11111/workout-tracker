"""
Auth endpoints.

Handles the OIDC login flow with Authentik, including redirect to
the authorization endpoint, callback handling, and token refresh.
"""

import logging
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.auth.oidc import get_oidc_config, validate_token
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.api.schemas import LoginUrlResponse, TokenResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/login", response_model=LoginUrlResponse)
async def login():
    """
    Redirect the client to the Authentik authorization endpoint.

    Returns the full authorization URL that the frontend should
    redirect the user to. Uses OIDC discovery to build the URL
    dynamically.
    """
    if not settings.OIDC_ISSUER_URL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sign-in is not configured. Set OIDC_ISSUER_URL to enable authentication.",
        )

    config = await get_oidc_config()
    authorization_endpoint = config.get("authorization_endpoint")

    if not authorization_endpoint:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not discover authorization endpoint from OIDC provider",
        )

    params = {
        "client_id": settings.OIDC_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": settings.OIDC_REDIRECT_URI,
        "scope": "openid profile email",
        "state": secrets.token_urlsafe(32),
    }

    authorization_url = f"{authorization_endpoint}?{urlencode(params)}"

    return LoginUrlResponse(authorization_url=authorization_url)


@router.get("/callback", response_model=TokenResponse)
async def callback(
    code: str = Query(..., description="Authorization code from OIDC provider"),
    state: str | None = Query(None, description="State parameter for CSRF protection"),
    db: Session = Depends(get_db),
):
    """
    Handle the OIDC callback after the user authorizes with Authentik.

    Exchanges the authorization code for tokens (access_token,
    id_token, refresh_token) and returns them to the frontend.
    Also creates or updates the user record in the database.
    """
    config = await get_oidc_config()
    token_endpoint = config.get("token_endpoint")

    if not token_endpoint:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not discover token endpoint from OIDC provider",
        )

    # Exchange the code for tokens
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.OIDC_REDIRECT_URI,
        "client_id": settings.OIDC_CLIENT_ID,
        "client_secret": settings.OIDC_CLIENT_SECRET,
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                token_endpoint,
                data=token_data,
                timeout=15,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Token exchange failed: %d %s",
                exc.response.status_code,
                exc.response.text,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to exchange authorization code for tokens",
            )
        except httpx.RequestError as exc:
            logger.error("Token exchange request error: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not reach OIDC token endpoint",
            )

    tokens = resp.json()
    access_token = tokens.get("access_token")
    id_token = tokens.get("id_token")
    refresh_token = tokens.get("refresh_token")
    expires_in = tokens.get("expires_in")

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No access_token in token response",
        )

    # Validate the token and extract user info
    # Use the id_token if available (more user claims), fall back to access_token
    token_to_validate = id_token or access_token
    try:
        payload = await validate_token(token_to_validate)
    except HTTPException:
        # If id_token validation fails, try the access_token
        if id_token and id_token != access_token:
            payload = await validate_token(access_token)
        else:
            raise

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No sub claim in token",
        )

    # Create or update user
    user = db.query(User).filter(User.authentik_sub == sub).first()
    if not user:
        user = User(
            authentik_sub=sub,
            display_name=payload.get("name") or payload.get("preferred_username"),
            email=payload.get("email"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("Created new user from OIDC callback: sub=%s", sub)
    else:
        changed = False
        new_name = payload.get("name") or payload.get("preferred_username")
        new_email = payload.get("email")
        if new_name and user.display_name != new_name:
            user.display_name = new_name
            changed = True
        if new_email and user.email != new_email:
            user.email = new_email
            changed = True
        if changed:
            db.commit()
            db.refresh(user)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str = Query(..., description="Refresh token from previous auth"),
):
    """
    Refresh the access token using a refresh token.

    Exchanges the refresh token for a new access token via the
    OIDC provider's token endpoint.
    """
    config = await get_oidc_config()
    token_endpoint = config.get("token_endpoint")

    if not token_endpoint:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not discover token endpoint from OIDC provider",
        )

    token_data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": settings.OIDC_CLIENT_ID,
        "client_secret": settings.OIDC_CLIENT_SECRET,
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                token_endpoint,
                data=token_data,
                timeout=15,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Token refresh failed: %d %s",
                exc.response.status_code,
                exc.response.text,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to refresh token. It may have expired.",
            )
        except httpx.RequestError as exc:
            logger.error("Token refresh request error: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not reach OIDC token endpoint",
            )

    tokens = resp.json()

    return TokenResponse(
        access_token=tokens.get("access_token", ""),
        token_type="bearer",
        expires_in=tokens.get("expires_in"),
        refresh_token=tokens.get("refresh_token"),
    )
