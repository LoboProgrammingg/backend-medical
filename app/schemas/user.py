"""Schemas Pydantic para User."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """Schema base de usuário."""

    email: EmailStr = Field(..., description="Email do usuário")
    full_name: str = Field(..., min_length=3, max_length=255, description="Nome completo")


class UserCreate(UserBase):
    """Schema para criação de usuário."""

    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="Senha (mínimo 8 caracteres)",
    )


class UserUpdate(BaseModel):
    """Schema para atualização de usuário."""

    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=3, max_length=255)
    password: Optional[str] = Field(None, min_length=8, max_length=100)


class UserInDB(UserBase):
    """Schema de usuário no banco de dados."""

    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserResponse(UserBase):
    """Schema de resposta pública de usuário."""

    id: UUID
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}

