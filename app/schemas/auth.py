"""Schemas Pydantic para autenticação."""

from pydantic import BaseModel, Field


class Token(BaseModel):
    """Schema de token JWT."""

    access_token: str = Field(..., description="Access token JWT")
    token_type: str = Field(default="bearer", description="Tipo do token")


class TokenData(BaseModel):
    """Dados extraídos do token JWT."""

    user_id: str | None = None


class LoginRequest(BaseModel):
    """Schema para requisição de login."""

    email: str = Field(..., description="Email do usuário")
    password: str = Field(..., description="Senha do usuário")


class LoginResponse(BaseModel):
    """Schema de resposta do login."""

    access_token: str
    token_type: str = "bearer"
    user: dict

