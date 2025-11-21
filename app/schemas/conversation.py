"""Schemas de Conversas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MessageBase(BaseModel):
    """Schema base de mensagem."""

    role: str = Field(..., description="'user' ou 'assistant'")
    content: str = Field(..., description="Conteúdo da mensagem")


class MessageCreate(MessageBase):
    """Schema para criar mensagem."""

    pass


class MessageResponse(MessageBase):
    """Schema de resposta de mensagem."""

    id: UUID
    conversation_id: UUID
    created_at: datetime

    class Config:
        """Config."""

        from_attributes = True


class ConversationBase(BaseModel):
    """Schema base de conversa."""

    title: str = Field(..., max_length=200, description="Título da conversa")


class ConversationCreate(ConversationBase):
    """Schema para criar conversa."""

    pass


class ConversationUpdate(BaseModel):
    """Schema para atualizar conversa."""

    title: str | None = Field(None, max_length=200)


class ConversationResponse(ConversationBase):
    """Schema de resposta de conversa."""

    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    class Config:
        """Config."""

        from_attributes = True


class ConversationWithMessages(ConversationResponse):
    """Schema de conversa com mensagens."""

    messages: list[MessageResponse] = []

    class Config:
        """Config."""

        from_attributes = True


class ConversationListResponse(BaseModel):
    """Schema de resposta de listagem de conversas."""

    conversations: list[ConversationResponse]
    total: int
    page: int
    page_size: int

