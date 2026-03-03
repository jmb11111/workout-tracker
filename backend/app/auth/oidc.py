from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.orm import Session
import httpx
from typing import Optional
from functools import lru_cache

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

security = HTTPBearer(auto_error=False)

_jwks_cache: Optional[dict] = None
_oidc_config_cache: Optional[dict] = None


async def get_oidc_config() -> dict:
    global _oidc_config_cache
    if _oidc_config_cache:
        return _oidc_config_cache
    async with httpx.AsyncClient() as client:
        url = f"{settings.OIDC_ISSUER_URL}/.well-known/openid-configuration"
        resp = await client.get(url, timeout=10)
        resp.raise_for_status()
        _oidc_config_cache = resp.json()
        return _oidc_config_cache


async def get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    config = await get_oidc_config()
    async with httpx.AsyncClient() as client:
        resp = await client.get(config["jwks_uri"], timeout=10)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        return _jwks_cache


def clear_oidc_cache():
    global _jwks_cache, _oidc_config_cache
    _jwks_cache = None
    _oidc_config_cache = None


async def validate_token(token: str) -> dict:
    try:
        jwks = await get_jwks()
        config = await get_oidc_config()
        header = jwt.get_unverified_header(token)
        key = None
        for k in jwks.get("keys", []):
            if k["kid"] == header.get("kid"):
                key = k
                break
        if not key:
            clear_oidc_cache()
            jwks = await get_jwks()
            for k in jwks.get("keys", []):
                if k["kid"] == header.get("kid"):
                    key = k
                    break
        if not key:
            raise HTTPException(status_code=401, detail="Unable to find signing key")
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=settings.OIDC_CLIENT_ID,
            issuer=config["issuer"],
        )
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = await validate_token(credentials.credentials)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="No sub claim in token")

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

    return user


async def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not credentials:
        return None
    try:
        return await get_current_user(request, credentials, db)
    except HTTPException:
        return None
