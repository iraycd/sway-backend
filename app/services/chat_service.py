import httpx
import json
from fastapi import WebSocket
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import uuid

from app.core.config import settings
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.conversation import ConversationCreate
from app.schemas.message import MessageCreate, MessageResponse
from app.services.conversation_analyzer import ConversationAnalyzer
from app.services.response_processor import ResponseProcessor
from app.services.therapy_prompt import TherapyPrompt
from app.services.translation_service import TranslationService


class ChatService:
    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.api_endpoint = settings.OPENROUTER_API_ENDPOINT
        self.model_name = settings.OPENROUTER_MODEL_NAME

        # Initialize supporting services
        self.conversation_analyzer = ConversationAnalyzer(api_key=self.api_key)
        self.response_processor = ResponseProcessor(api_key=self.api_key)
        self.translation_service = TranslationService(api_key=self.api_key)

        print(f"ChatService: Initialized with API key: {self.api_key[:5]}...")
        print(f"ChatService: Using endpoint: {self.api_endpoint}")
        print(f"ChatService: Using model: {self.model_name}")

    def create_conversation(self, db: Session, conversation: ConversationCreate) -> Conversation:
        """Create a new conversation"""
        db_conversation = Conversation(name=conversation.name)
        db.add(db_conversation)
        db.commit()
        db.refresh(db_conversation)
        return db_conversation

    def get_conversation(self, db: Session, conversation_id: uuid.UUID) -> Optional[Conversation]:
        """Get a conversation by ID"""
        return db.query(Conversation).filter(Conversation.id == conversation_id).first()

    def get_conversations(self, db: Session, skip: int = 0, limit: int = 100) -> List[Conversation]:
        """Get all conversations with pagination"""
        return db.query(Conversation).offset(skip).limit(limit).all()

    def get_messages(self, db: Session, conversation_id: uuid.UUID, skip: int = 0, limit: int = 100) -> List[Message]:
        """Get all messages for a conversation with pagination"""
        return db.query(Message).filter(Message.conversation_id == conversation_id).offset(skip).limit(limit).all()

    async def process_message(self, db: Session, conversation_id: uuid.UUID, message: MessageCreate) -> List[Message]:
        """
        Process a user message and generate AI responses

        This method implements the full multi-layered approach:
        1. Layer 1: Analyze the conversation and classify the query
        2. Layer 2: Get the appropriate prompt based on analysis
        3. Layer 3: Process the response into multiple natural messages
        """
        # Check if conversation exists
        conversation = self.get_conversation(db, conversation_id)
        if not conversation:
            raise ValueError(
                f"Conversation with ID {conversation_id} not found")

        # Save user message to database
        user_message = Message(
            conversation_id=conversation_id,
            content=message.content,
            sender_id=message.sender_id,
            is_user=True
        )
        db.add(user_message)
        db.commit()
        db.refresh(user_message)

        # Get conversation history
        conversation_history = self.get_messages(db, conversation_id)

        # Process the message through the multi-layered approach
        try:
            # Layer 1: Analyze the conversation
            analysis = await self.conversation_analyzer.analyze_conversation(
                message.content,
                conversation_history
            )

            # Layer 2: Get the appropriate prompt
            if analysis['queryType'] == 'SIMPLE' and analysis['recommendedApproach'] == 'CONCISE':
                system_prompt = TherapyPrompt.get_concise_prompt()
            else:
                system_prompt = TherapyPrompt.get_analyzed_prompt(analysis)

            # Get raw response from AI
            raw_response = await self._get_raw_response(message.content, system_prompt, conversation_history)

            # Layer 3: Process the response into multiple messages
            response_messages = await self.response_processor.process_response(
                raw_response,
                analysis,
                message.content
            )

            # Save AI responses to database
            db_messages = []
            for response_text in response_messages:
                ai_message = Message(
                    conversation_id=conversation_id,
                    content=response_text,
                    sender_id="AI",
                    is_user=False
                )
                db.add(ai_message)
                db_messages.append(ai_message)

            db.commit()
            for msg in db_messages:
                db.refresh(msg)

            return db_messages

        except Exception as e:
            print(f"Error processing message: {str(e)}")
            # Save error message
            error_message = Message(
                conversation_id=conversation_id,
                content="Sorry, there was an error processing your message. Please try again.",
                sender_id="AI",
                is_user=False
            )
            db.add(error_message)
            db.commit()
            db.refresh(error_message)
            return [error_message]

    async def _get_raw_response(self, message: str, system_prompt: str, conversation_history: List[Message]) -> str:
        """Get a raw response from the AI model"""
        # Prepare conversation history for the API request
        message_history = []

        # Add system prompt
        message_history.append({"role": "system", "content": system_prompt})

        # Add conversation history (limited to last 10 messages to avoid token limits)
        history_limit = 10
        start_idx = max(0, len(conversation_history) - history_limit)

        for i in range(start_idx, len(conversation_history)):
            history_message = conversation_history[i]
            message_history.append({
                "role": "user" if history_message.is_user else "assistant",
                "content": history_message.content
            })

        # Add current user message if not already in history
        if not conversation_history or conversation_history[-1].is_user == False:
            message_history.append({"role": "user", "content": message})

        # Make API request
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.api_endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model_name,
                    "messages": message_history,
                },
                timeout=60.0,
            )

            if response.status_code != 200:
                print(
                    f"ChatService: API request failed with status: {response.status_code}")
                print(f"ChatService: Response body: {response.text}")
                raise Exception(
                    f"API request failed with status: {response.status_code}")

            response_data = response.json()
            return response_data["choices"][0]["message"]["content"]

    async def stream_response(self, websocket: WebSocket, db: Session, conversation_id: uuid.UUID, message: MessageCreate):
        """Stream a response to the user's message"""
        # Save user message to database
        user_message = Message(
            conversation_id=conversation_id,
            content=message.content,
            sender_id=message.sender_id,
            is_user=True
        )
        db.add(user_message)
        db.commit()
        db.refresh(user_message)

        # Get conversation history
        conversation_history = self.get_messages(db, conversation_id)

        try:
            # Layer 1: Analyze the conversation
            analysis = await self.conversation_analyzer.analyze_conversation(
                message.content,
                conversation_history
            )

            # Layer 2: Get the appropriate prompt
            if analysis['queryType'] == 'SIMPLE' and analysis['recommendedApproach'] == 'CONCISE':
                system_prompt = TherapyPrompt.get_concise_prompt()
            else:
                system_prompt = TherapyPrompt.get_analyzed_prompt(analysis)

            # Prepare message history for streaming
            message_history = []
            message_history.append(
                {"role": "system", "content": system_prompt})

            # Add conversation history (limited to last 10 messages)
            history_limit = 10
            start_idx = max(0, len(conversation_history) - history_limit)

            for i in range(start_idx, len(conversation_history)):
                history_message = conversation_history[i]
                message_history.append({
                    "role": "user" if history_message.is_user else "assistant",
                    "content": history_message.content
                })

            # Make streaming API request
            async with httpx.AsyncClient(timeout=None) as client:
                response = await client.post(
                    self.api_endpoint,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model_name,
                        "messages": message_history,
                        "stream": True,
                    },
                    timeout=None
                )

                if response.status_code != 200:
                    await websocket.send_json({
                        "error": f"API request failed with status: {response.status_code}"
                    })
                    return

                # Process the streaming response
                buffer = ""
                full_response = ""

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break

                        try:
                            parsed = json.loads(data)
                            content = parsed["choices"][0]["delta"].get(
                                "content", "")
                            if content:
                                buffer += content
                                full_response += content

                                # Send chunks to the client
                                await websocket.send_json({
                                    "type": "chunk",
                                    "content": content
                                })

                                # If we have a complete sentence or enough characters, save as a partial message
                                if buffer.endswith((".", "!", "?", "\n")) or len(buffer) > 100:
                                    buffer = ""

                        except json.JSONDecodeError:
                            print(f"Error parsing JSON: {data}")

                # Save the complete response to the database
                ai_message = Message(
                    conversation_id=conversation_id,
                    content=full_response,
                    sender_id="AI",
                    is_user=False
                )
                db.add(ai_message)
                db.commit()
                db.refresh(ai_message)

                # Send completion message
                await websocket.send_json({
                    "type": "complete",
                    "message_id": str(ai_message.id)
                })

        except Exception as e:
            print(f"Error in stream_response: {str(e)}")
            await websocket.send_json({
                "error": "Sorry, there was an error processing your message."
            })

            # Save error message to database
            error_message = Message(
                conversation_id=conversation_id,
                content="Sorry, there was an error processing your message. Please try again.",
                sender_id="AI",
                is_user=False
            )
            db.add(error_message)
            db.commit()
            db.refresh(error_message)
