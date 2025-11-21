"""Schemas Pydantic para Note."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class NoteBase(BaseModel):
    """Schema base de anotação."""

    title: str = Field(..., min_length=1, max_length=500, description="Título da anotação")
    content: str = Field(..., min_length=1, description="Conteúdo da anotação")
    tags: list[str] = Field(default_factory=list, description="Tags da anotação")
    is_favorite: bool = Field(default=False, description="Anotação favorita")


class NoteCreate(NoteBase):
    """Schema para criação de anotação."""

    pass


class NoteUpdate(BaseModel):
    """Schema para atualização de anotação."""

    title: Optional[str] = Field(None, min_length=1, max_length=500)
    content: Optional[str] = Field(None, min_length=1)
    tags: Optional[list[str]] = None
    is_favorite: Optional[bool] = None


class NoteInDB(NoteBase):
    """Schema de anotação no banco de dados."""

    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NoteResponse(NoteBase):
    """Schema de resposta pública de anotação."""

    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NoteListResponse(BaseModel):
    """Schema de resposta para lista de anotações."""

    notes: list[NoteResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

