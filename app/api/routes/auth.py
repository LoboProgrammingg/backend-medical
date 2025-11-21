"""Rotas de autenticação."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse
from app.schemas.user import UserCreate, UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post(
    "/register",
    response_model=LoginResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar novo usuário",
    description="Cria uma nova conta de usuário no sistema e retorna um token JWT.",
)
async def register(
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponse:
    """
    Registra um novo usuário.

    Args:
        user_data: Dados do usuário a ser criado.
        db: Sessão do banco de dados.

    Returns:
        LoginResponse: Token JWT e dados do usuário criado.
    """
    user = await AuthService.register_user(user_data, db)
    # Criar token JWT para o novo usuário
    from app.core.security import create_access_token
    access_token = create_access_token(data={"sub": str(user.id)})
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=user.model_dump(),  # Converter UserResponse para dict
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Fazer login",
    description="Autentica um usuário e retorna um token JWT.",
)
async def login(
    login_data: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponse:
    """
    Autentica um usuário.

    Args:
        login_data: Credenciais de login (email e senha).
        db: Sessão do banco de dados.

    Returns:
        LoginResponse: Token JWT e dados do usuário.
    """
    return await AuthService.authenticate_user(login_data, db)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Obter usuário atual",
    description="Retorna os dados do usuário autenticado.",
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """
    Retorna dados do usuário autenticado.

    Args:
        current_user: Usuário obtido do token JWT.

    Returns:
        UserResponse: Dados do usuário.
    """
    return UserResponse.model_validate(current_user)

