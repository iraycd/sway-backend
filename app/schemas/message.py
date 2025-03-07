from datetime import datetime
from typing import List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, validator


# Shared properties
class MessageBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)
    is_user: bool = True
    sender_id: Optional[str] = Field(None, max_length=255)

    @validator("content")
    def validate_content(cls, v):
        if not v or v.strip() == "":
            raise ValueError("Message content cannot be empty")
        return v


# Properties to receive on message creation
class MessageCreate(MessageBase):
    pass


# Properties to return to client
class MessageResponse(MessageBase):
    id: uuid.UUID
    conversation_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Properties for message list
class MessageList(BaseModel):
    messages: List[MessageResponse]
