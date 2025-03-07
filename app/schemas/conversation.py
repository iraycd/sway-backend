from datetime import datetime
from typing import List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, validator


# Shared properties
class ConversationBase(BaseModel):
    name: Optional[str] = Field(None, max_length=100)

    @validator("name")
    def validate_name(cls, v):
        if v is not None and v.strip() == "":
            return None
        return v


# Properties to receive on conversation creation
class ConversationCreate(ConversationBase):
    pass


# Properties to return to client
class ConversationResponse(ConversationBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Properties for conversation list
class ConversationList(BaseModel):
    conversations: List[ConversationResponse]
