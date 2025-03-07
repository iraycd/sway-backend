import time
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from typing import Optional
import requests

from app.db.session import get_db
from app.models.user import User, AuthProvider
from app.schemas.auth import AuthRequest, AuthResponse, TokenPayload
from app.services.auth import create_access_token, verify_google_token, verify_apple_token
from app.core.config import settings

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """
    Get the current authenticated user
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY,
                             algorithms=[settings.ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_payload = TokenPayload(sub=user_id)
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == token_payload.sub).first()
    if user is None:
        raise credentials_exception
    return user


@router.get("/callbacks/sign_in_with_apple")
async def apple_callback(request: Request, code: str = None, state: str = None, db: Session = Depends(get_db)):
    """
    Handle the callback from Apple Sign-In for web authentication
    """
    if not code:
        raise HTTPException(
            status_code=400, detail="Authorization code is required")

    try:
        # Exchange the authorization code for tokens
        token_response = await exchange_apple_code_for_token(code)

        # Validate the ID token
        id_token = token_response.get("id_token")
        if not id_token:
            raise HTTPException(
                status_code=400, detail="ID token not received from Apple")

        # Verify the token and extract user info
        user_info = await verify_apple_token(id_token)

        # Create or get user
        user = await get_or_create_apple_user(user_info, db)

        # Generate JWT token
        access_token = create_access_token(data={"sub": str(user.id)})

        # Redirect to the frontend with the token
        # You can use a custom URL scheme or a specific page in your app
        frontend_url = f"https://sway.teja.app/#/auth-callback?token={access_token}&user_id={user.id}"
        return RedirectResponse(url=frontend_url)

    except Exception as e:
        # Log the error
        print(f"Apple callback error: {e}")
        # Redirect to error page
        return RedirectResponse(url="https://sway.teja.app/#/auth-error")


async def exchange_apple_code_for_token(code: str):
    """
    Exchange the authorization code for tokens from Apple
    """
    # This is where you'll use your client_secret generated with your private key
    client_secret = generate_apple_client_secret()

    token_request_data = {
        "client_id": settings.APPLE_CLIENT_ID,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": "https://sai.teja.app/api/auth/callbacks/sign_in_with_apple"
    }

    response = requests.post(
        "https://appleid.apple.com/auth/token",
        data=token_request_data
    )

    if response.status_code != 200:
        raise HTTPException(
            status_code=400, detail="Failed to exchange code for token")

    return response.json()


def generate_apple_client_secret():
    """
    Generate the client secret for Apple Sign-In

    This requires:
    - Your Apple Developer Team ID
    - Your Apple Services ID (client_id)
    - Your private key ID from Apple
    - Your private key file
    """
    # Current time
    now = int(time.time())

    # Prepare the token payload
    payload = {
        'iss': settings.APPLE_TEAM_ID,
        'iat': now,
        'exp': now + 86400 * 180,  # 180 days
        'aud': 'https://appleid.apple.com',
        'sub': settings.APPLE_CLIENT_ID,
    }

    # Read the private key
    with open(settings.APPLE_PRIVATE_KEY_PATH, 'r') as key_file:
        private_key = key_file.read()

    # Create the client secret
    client_secret = jwt.encode(
        payload,
        private_key,
        algorithm='ES256',
        headers={
            'kid': settings.APPLE_KEY_ID
        }
    )

    return client_secret


async def get_or_create_apple_user(user_info, db: Session):
    """
    Get existing user or create a new one based on Apple user info
    """
    provider_user_id = user_info["provider_user_id"]
    email = user_info.get("email")

    # Check if this provider account exists
    auth_provider = db.query(AuthProvider).filter(
        AuthProvider.provider_type == "apple",
        AuthProvider.provider_user_id == provider_user_id
    ).first()

    if auth_provider:
        # User exists, return user
        return auth_provider.user
    else:
        # Create new user and auth provider
        user = User()
        db.add(user)
        db.flush()

        auth_provider = AuthProvider(
            user_id=user.id,
            provider_type="apple",
            provider_user_id=provider_user_id,
            email=email
        )
        db.add(auth_provider)
        db.commit()

        return user


@router.post("/mock-apple-signin", response_model=AuthResponse)
async def mock_apple_signin(db: Session = Depends(get_db)):
    """
    Mock Apple Sign-In for local development
    """
    # Create or get user with mock data
    provider_user_id = "mock-apple-user-id"
    email = "mock-user@example.com"

    # Check if this provider account exists
    auth_provider = db.query(AuthProvider).filter(
        AuthProvider.provider_type == "apple",
        AuthProvider.provider_user_id == provider_user_id
    ).first()

    if auth_provider:
        # User exists, return token
        user = auth_provider.user
    else:
        # Create new user and auth provider
        user = User()
        db.add(user)
        db.flush()

        auth_provider = AuthProvider(
            user_id=user.id,
            provider_type="apple",
            provider_user_id=provider_user_id,
            email=email
        )
        db.add(auth_provider)
        db.commit()

    # Generate JWT token
    token = create_access_token(data={"sub": str(user.id)})

    return {"access_token": token, "token_type": "bearer", "user_id": str(user.id)}


@router.post("/signin", response_model=AuthResponse)
async def signin(auth_request: AuthRequest, db: Session = Depends(get_db)):
    """
    Sign in or sign up a user with a third-party provider
    """
    # Verify the token
    user_info = None
    if auth_request.provider_type == "google":
        user_info = await verify_google_token(auth_request.id_token)
    elif auth_request.provider_type == "apple":
        user_info = await verify_apple_token(auth_request.id_token)
    else:
        raise HTTPException(
            status_code=400, detail="Unsupported provider type")

    if not user_info:
        raise HTTPException(
            status_code=401, detail="Invalid authentication token")

    # Override with verified data
    provider_user_id = user_info["provider_user_id"]
    email = user_info.get("email")

    # Check if this provider account exists
    auth_provider = db.query(AuthProvider).filter(
        AuthProvider.provider_type == auth_request.provider_type,
        AuthProvider.provider_user_id == provider_user_id
    ).first()

    if auth_provider:
        # User exists, return token
        user = auth_provider.user
    else:
        # Create new user and auth provider
        user = User()
        db.add(user)
        db.flush()

        auth_provider = AuthProvider(
            user_id=user.id,
            provider_type=auth_request.provider_type,
            provider_user_id=provider_user_id,
            email=email
        )
        db.add(auth_provider)
        db.commit()

    # Generate JWT token
    token = create_access_token(data={"sub": str(user.id)})

    return {"access_token": token, "token_type": "bearer", "user_id": str(user.id)}


@router.post("/link-account", response_model=AuthResponse)
async def link_account(
    auth_request: AuthRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Link a new provider account to an existing user
    """
    # Verify the token
    user_info = None
    if auth_request.provider_type == "google":
        user_info = await verify_google_token(auth_request.id_token)
    elif auth_request.provider_type == "apple":
        user_info = await verify_apple_token(auth_request.id_token)
    else:
        raise HTTPException(
            status_code=400, detail="Unsupported provider type")

    if not user_info:
        raise HTTPException(
            status_code=401, detail="Invalid authentication token")

    # Override with verified data
    provider_user_id = user_info["provider_user_id"]
    email = user_info.get("email")

    # Check if this provider account already exists
    existing_provider = db.query(AuthProvider).filter(
        AuthProvider.provider_type == auth_request.provider_type,
        AuthProvider.provider_user_id == provider_user_id
    ).first()

    if existing_provider:
        if existing_provider.user_id != current_user.id:
            raise HTTPException(
                status_code=400, detail="This account is already linked to another user")
        return {
            "access_token": create_access_token(data={"sub": str(current_user.id)}),
            "token_type": "bearer",
            "user_id": str(current_user.id)
        }

    # Create new auth provider for current user
    auth_provider = AuthProvider(
        user_id=current_user.id,
        provider_type=auth_request.provider_type,
        provider_user_id=provider_user_id,
        email=email
    )
    db.add(auth_provider)
    db.commit()

    return {
        "access_token": create_access_token(data={"sub": str(current_user.id)}),
        "token_type": "bearer",
        "user_id": str(current_user.id)
    }
