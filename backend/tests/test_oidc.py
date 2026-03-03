"""Tests for OIDC token validation."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from jose import jwt
from datetime import datetime, timezone, timedelta

from app.auth.oidc import validate_token, clear_oidc_cache


# RSA key pair for testing (not used in production)
TEST_KID = "test-key-id"
TEST_ISSUER = "https://auth.example.com/application/o/test/"
TEST_CLIENT_ID = "test-client-id"

MOCK_OIDC_CONFIG = {
    "issuer": TEST_ISSUER,
    "jwks_uri": f"{TEST_ISSUER}.well-known/jwks.json",
    "authorization_endpoint": f"{TEST_ISSUER}authorize/",
    "token_endpoint": f"{TEST_ISSUER}token/",
}


def _make_token(payload: dict, secret: str = "test-secret") -> str:
    """Create a test JWT (using HMAC for simplicity in tests)."""
    return jwt.encode(
        payload,
        secret,
        algorithm="HS256",
        headers={"kid": TEST_KID},
    )


@pytest.fixture(autouse=True)
def clear_cache():
    clear_oidc_cache()
    yield
    clear_oidc_cache()


class TestTokenValidation:
    @pytest.mark.asyncio
    async def test_valid_token_returns_payload(self):
        payload = {
            "sub": "user-123",
            "name": "Test User",
            "email": "test@example.com",
            "iss": TEST_ISSUER,
            "aud": TEST_CLIENT_ID,
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.now(timezone.utc).timestamp()),
        }
        secret = "test-secret"
        token = _make_token(payload, secret)

        mock_jwks = {
            "keys": [
                {
                    "kid": TEST_KID,
                    "kty": "oct",
                    "k": secret,
                }
            ]
        }

        with patch("app.auth.oidc.get_jwks", new_callable=AsyncMock, return_value=mock_jwks), \
             patch("app.auth.oidc.get_oidc_config", new_callable=AsyncMock, return_value=MOCK_OIDC_CONFIG), \
             patch("app.auth.oidc.settings") as mock_settings, \
             patch("jose.jwt.decode", return_value=payload):
            mock_settings.OIDC_CLIENT_ID = TEST_CLIENT_ID
            result = await validate_token(token)
            assert result["sub"] == "user-123"
            assert result["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_expired_token_raises(self):
        payload = {
            "sub": "user-123",
            "iss": TEST_ISSUER,
            "aud": TEST_CLIENT_ID,
            "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
            "iat": int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()),
        }
        token = _make_token(payload)

        mock_jwks = {"keys": [{"kid": TEST_KID, "kty": "oct", "k": "test-secret"}]}

        with patch("app.auth.oidc.get_jwks", new_callable=AsyncMock, return_value=mock_jwks), \
             patch("app.auth.oidc.get_oidc_config", new_callable=AsyncMock, return_value=MOCK_OIDC_CONFIG), \
             patch("app.auth.oidc.settings") as mock_settings:
            mock_settings.OIDC_CLIENT_ID = TEST_CLIENT_ID
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await validate_token(token)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_unknown_kid_retries_jwks(self):
        """When the kid isn't found, it should clear cache and retry JWKS fetch."""
        payload = {
            "sub": "user-456",
            "iss": TEST_ISSUER,
            "aud": TEST_CLIENT_ID,
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        }
        token = _make_token(payload)

        empty_jwks = {"keys": []}
        real_jwks = {"keys": [{"kid": TEST_KID, "kty": "oct", "k": "test-secret"}]}

        call_count = 0

        async def mock_get_jwks():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return empty_jwks
            return real_jwks

        with patch("app.auth.oidc.get_jwks", side_effect=mock_get_jwks), \
             patch("app.auth.oidc.get_oidc_config", new_callable=AsyncMock, return_value=MOCK_OIDC_CONFIG), \
             patch("app.auth.oidc.settings") as mock_settings, \
             patch("jose.jwt.decode", return_value=payload):
            mock_settings.OIDC_CLIENT_ID = TEST_CLIENT_ID
            result = await validate_token(token)
            assert result["sub"] == "user-456"
            assert call_count == 2
