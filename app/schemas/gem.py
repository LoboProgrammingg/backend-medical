"""Schemas para Gems (IAs Especializadas)."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class GemDocumentResponse(BaseModel):
    """Schema de resposta de documento da Gem."""

    id: UUID
    filename: str
    file_size: int
    created_at: str

    class Config:
        from_attributes = True


class GemCreate(BaseModel):
    """Schema para criar Gem."""

    name: str = Field(..., description="Nome da Gem", max_length=255)
    description: Optional[str] = Field(None, description="Descrição da Gem")
    instructions: str = Field(..., description="Instruções personalizadas para a IA")


class GemUpdate(BaseModel):
    """Schema para atualizar Gem."""

    name: Optional[str] = Field(None, description="Nome da Gem", max_length=255)
    description: Optional[str] = Field(None, description="Descrição da Gem")
    instructions: Optional[str] = Field(None, description="Instruções personalizadas para a IA")


class GemResponse(BaseModel):
    """Schema de resposta de Gem."""

    id: UUID
    name: str
    description: Optional[str]
    instructions: str
    documents: List[GemDocumentResponse] = []
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class GemListResponse(BaseModel):
    """Schema de resposta de lista de Gems."""

    gems: List[GemResponse]
    total: int


class GemChatRequest(BaseModel):
    """Schema para chat com Gem."""

    message: str = Field(..., description="Mensagem do usuário")
    gem_id: UUID = Field(..., description="ID da Gem a ser usada")


class GemChatResponse(BaseModel):
    """Schema de resposta do chat com Gem."""

    response: str
    gem_id: UUID
    gem_name: str
    sources_used: List[str] = []

