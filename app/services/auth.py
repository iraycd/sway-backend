import requests
from jose import jwt
from datetime import datetime, timedelta
from typing import Optional
from app.core.config import settings


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    Create a JWT access token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def verify_google_token(id_token: str):
    """
    Verify Google ID token

    In production, you should use the google-auth library for more robust verification
    """
    try:
        # Google's public keys endpoint
        google_certs_url = "https://www.googleapis.com/oauth2/v1/certs"
        response = requests.get(google_certs_url)
        certs = response.json()

        # Decode and verify the token
        header = jwt.get_unverified_header(id_token)
        key_id = header.get("kid")
        if not key_id or key_id not in certs:
            return None

        payload = jwt.decode(
            id_token,
            certs[key_id],
            algorithms=["RS256"],
            audience=settings.GOOGLE_CLIENT_ID,
        )

        return {
            "provider_user_id": payload["sub"],
            "email": payload.get("email"),
        }
    except Exception as e:
        print(f"Google token verification error: {e}")
        return None


async def verify_apple_token(id_token: str):
    """
    Verify Apple ID token
    """
    try:
        # Apple's public keys endpoint
        apple_keys_url = "https://appleid.apple.com/auth/keys"
        response = requests.get(apple_keys_url)
        keys = response.json()

        # Decode and verify the token
        header = jwt.get_unverified_header(id_token)
        key_id = header.get("kid")

        # Find the matching key
        key = None
        for k in keys["keys"]:
            if k["kid"] == key_id:
                key = k
                break

        if not key:
            return None

        payload = jwt.decode(
            id_token,
            key,
            algorithms=["RS256"],
            audience=settings.APPLE_CLIENT_ID,
        )

        return {
            "provider_user_id": payload["sub"],
            "email": payload.get("email"),
        }
    except Exception as e:
        print(f"Apple token verification error: {e}")
        return None
