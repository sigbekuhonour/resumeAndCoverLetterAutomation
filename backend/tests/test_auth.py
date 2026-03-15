import pytest
from jose import jwt
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
import asyncio
import os

# Set test env vars before importing settings
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-that-is-long-enough")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.setdefault("TAVILY_API_KEY", "test-tavily-key")
os.environ.setdefault("FIRECRAWL_API_KEY", "test-firecrawl-key")

from config import settings
from auth import get_current_user


def make_token(user_id: str, secret: str = None) -> str:
    """Create a test JWT."""
    return jwt.encode(
        {"sub": user_id, "aud": "authenticated"},
        secret or settings.supabase_jwt_secret,
        algorithm="HS256",
    )


def test_valid_token_returns_user_id():
    token = make_token("test-user-123")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    result = asyncio.run(get_current_user(creds))
    assert result == "test-user-123"


def test_invalid_token_raises_401():
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad-token")
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_current_user(creds))
    assert exc_info.value.status_code == 401
