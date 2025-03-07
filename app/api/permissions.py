from fastapi import HTTPException, status, Depends
from sqlalchemy.orm import Session
import uuid

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.conversation import Conversation


async def get_current_user_or_raise(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get the current authenticated user or raise an exception.
    This is useful when you want to ensure a user is authenticated.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


async def verify_conversation_owner(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_raise),
) -> Conversation:
    """
    Verify that the current user owns the conversation.
    Returns the conversation if the user is the owner, otherwise raises an exception.
    """
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id).first()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    if conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this conversation"
        )

    return conversation


async def verify_message_access(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_raise),
) -> Conversation:
    """
    Verify that the current user has access to messages in the conversation.
    This is a wrapper around verify_conversation_owner for semantic clarity.
    """
    return await verify_conversation_owner(conversation_id, db, current_user)
