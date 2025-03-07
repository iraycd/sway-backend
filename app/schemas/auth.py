from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional, Literal
from uuid import UUID


class AuthRequest(BaseModel):
    provider_type: Literal["google", "apple"]
    provider_user_id: str = Field(..., min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    id_token: str = Field(..., min_length=10)

    @validator("id_token")
    def validate_id_token(cls, v):
        if not v or len(v.strip()) < 10:
            raise ValueError("ID token must be a valid token string")
        return v


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: str


class TokenPayload(BaseModel):
    sub: Optional[str] = None
