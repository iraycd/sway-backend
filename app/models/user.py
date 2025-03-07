from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow,
                        onupdate=datetime.utcnow)

    # Relationships
    auth_providers = relationship(
        "AuthProvider", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user")


class AuthProvider(Base):
    __tablename__ = "auth_providers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    provider_type = Column(String, nullable=False)  # "google" or "apple"
    provider_user_id = Column(String, nullable=False)  # ID from the provider
    email = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="auth_providers")

    # Unique constraint to prevent duplicate provider accounts
    __table_args__ = (
        UniqueConstraint('provider_type', 'provider_user_id',
                         name='unique_provider_account'),
    )
