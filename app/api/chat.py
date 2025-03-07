from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from app.db.session import get_db
from app.schemas.message import MessageCreate, MessageResponse
from app.schemas.conversation import ConversationCreate, ConversationResponse, ConversationList
from app.services.chat_service import ChatService
from app.api.dependencies import get_chat_service
from app.api.auth import get_current_user
from app.api.permissions import verify_conversation_owner, verify_message_access, get_current_user_or_raise
from app.models.user import User
from app.models.conversation import Conversation

router = APIRouter()


@router.post("/conversations/", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    conversation: ConversationCreate,
    db: Session = Depends(get_db),
    chat_service: ChatService = Depends(get_chat_service),
    current_user: User = Depends(get_current_user_or_raise)
):
    """
    Create a new conversation for the authenticated user.
    """
    return chat_service.create_conversation(db, conversation, current_user.id)


@router.get("/conversations/", response_model=List[ConversationResponse])
async def get_conversations(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    chat_service: ChatService = Depends(get_chat_service),
    current_user: User = Depends(get_current_user_or_raise)
):
    """
    Get all conversations for the authenticated user with pagination.
    """
    return chat_service.get_user_conversations(db, current_user.id, skip=skip, limit=limit)


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    chat_service: ChatService = Depends(get_chat_service),
    conversation: Conversation = Depends(verify_conversation_owner)
):
    """
    Get a conversation by ID if the user is the owner.
    """
    return conversation


@router.post("/conversations/{conversation_id}/messages/", response_model=List[MessageResponse])
async def create_message(
    conversation_id: uuid.UUID,
    message: MessageCreate,
    db: Session = Depends(get_db),
    chat_service: ChatService = Depends(get_chat_service),
    conversation: Conversation = Depends(verify_conversation_owner)
):
    """
    Create a new message in a conversation and get AI responses.
    Only the conversation owner can create messages.
    """
    try:
        return await chat_service.process_message(db, conversation_id, message)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An error occurred: {str(e)}")


@router.get("/conversations/{conversation_id}/messages/", response_model=List[MessageResponse])
async def get_messages(
    conversation_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    chat_service: ChatService = Depends(get_chat_service),
    conversation: Conversation = Depends(verify_conversation_owner)
):
    """
    Get all messages for a conversation with pagination.
    Only the conversation owner can access messages.
    """
    return chat_service.get_messages(db, conversation_id, skip=skip, limit=limit)


@router.websocket("/ws/{conversation_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    conversation_id: uuid.UUID,
    token: str = Query(...),
    db: Session = Depends(get_db),
    chat_service: ChatService = Depends(get_chat_service)
):
    """
    WebSocket endpoint for streaming responses.
    Requires authentication token and conversation ownership.
    """
    await websocket.accept()

    # Verify token and get user
    try:
        from app.api.auth import jwt, settings, TokenPayload
        payload = jwt.decode(token, settings.SECRET_KEY,
                             algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            await websocket.send_json({"error": "Invalid authentication token"})
            await websocket.close()
            return

        # Check if conversation exists and user owns it
        conversation = chat_service.get_conversation(db, conversation_id)
        if not conversation:
            await websocket.send_json({"error": "Conversation not found"})
            await websocket.close()
            return

        if conversation.user_id != uuid.UUID(user_id):
            await websocket.send_json({"error": "Not authorized to access this conversation"})
            await websocket.close()
            return
    except Exception as e:
        await websocket.send_json({"error": f"Authentication error: {str(e)}"})
        await websocket.close()
        return

    try:
        while True:
            data = await websocket.receive_json()

            # Validate the received data
            if "content" not in data:
                await websocket.send_json({"error": "Message content is required"})
                continue

            message = MessageCreate(
                content=data["content"],
                sender_id=data.get("sender_id"),
                is_user=True
            )

            # Process the message and stream AI responses
            await chat_service.stream_response(websocket, db, conversation_id, message)
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for conversation {conversation_id}")
    except Exception as e:
        print(f"Error in WebSocket: {str(e)}")
        try:
            await websocket.send_json({"error": f"An error occurred: {str(e)}"})
        except Exception:
            pass  # Connection might already be closed
