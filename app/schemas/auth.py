from pydantic import BaseModel
from typing import Optional
from uuid import UUID


class AuthRequest(BaseModel):
    provider_type: str  # "google" or "apple"
    provider_user_id: str
    email: Optional[str] = None
    id_token: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: str


class TokenPayload(BaseModel):
    sub: Optional[str] = None
