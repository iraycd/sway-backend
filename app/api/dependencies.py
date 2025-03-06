from app.services.chat_service import ChatService


def get_chat_service() -> ChatService:
    """
    Dependency to get a ChatService instance.
    """
    return ChatService()
