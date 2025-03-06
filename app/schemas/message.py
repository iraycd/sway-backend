from datetime import datetime
from typing import List, Optional
import uuid

from pydantic import BaseModel, ConfigDict


# Shared properties
class MessageBase(BaseModel):
    content: str
    is_user: bool = True
    sender_id: Optional[str] = None


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
