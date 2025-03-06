from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from app.db.session import get_db
from app.schemas.message import MessageCreate, MessageResponse
from app.schemas.conversation import ConversationCreate, ConversationResponse, ConversationList
from app.services.chat_service import ChatService
from app.api.dependencies import get_chat_service

router = APIRouter()


@router.post("/conversations/", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    conversation: ConversationCreate,
    db: Session = Depends(get_db),
    chat_service: ChatService = Depends(get_chat_service)
):
    """
    Create a new conversation.
    """
    return chat_service.create_conversation(db, conversation)


@router.get("/conversations/", response_model=List[ConversationResponse])
async def get_conversations(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    chat_service: ChatService = Depends(get_chat_service)
):
    """
    Get all conversations with pagination.
    """
    return chat_service.get_conversations(db, skip=skip, limit=limit)


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    chat_service: ChatService = Depends(get_chat_service)
):
    """
    Get a conversation by ID.
    """
    conversation = chat_service.get_conversation(db, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.post("/conversations/{conversation_id}/messages/", response_model=List[MessageResponse])
async def create_message(
    conversation_id: uuid.UUID,
    message: MessageCreate,
    db: Session = Depends(get_db),
    chat_service: ChatService = Depends(get_chat_service)
):
    """
    Create a new message in a conversation and get AI responses.
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
    chat_service: ChatService = Depends(get_chat_service)
):
    """
    Get all messages for a conversation with pagination.
    """
    conversation = chat_service.get_conversation(db, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return chat_service.get_messages(db, conversation_id, skip=skip, limit=limit)


@router.websocket("/ws/{conversation_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    chat_service: ChatService = Depends(get_chat_service)
):
    """
    WebSocket endpoint for streaming responses.
    """
    await websocket.accept()

    # Check if conversation exists
    conversation = chat_service.get_conversation(db, conversation_id)
    if conversation is None:
        await websocket.send_json({"error": "Conversation not found"})
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
        except:
            pass  # Connection might already be closed
