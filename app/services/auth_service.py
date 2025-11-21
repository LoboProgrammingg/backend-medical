"""Service layer para autenticação."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse
from app.schemas.user import UserCreate, UserResponse
from app.utils.errors import AuthenticationError, ValidationError


class AuthService:
    """Service para operações de autenticação."""

    @staticmethod
    async def register_user(user_data: UserCreate, db: AsyncSession) -> UserResponse:
        """
        Registra um novo usuário no sistema.

        Args:
            user_data: Dados do usuário a ser criado.
            db: Sessão do banco de dados.

        Returns:
            UserResponse: Usuário criado.

        Raises:
            ValidationError: Se o email já estiver em uso.
        """
        # Verificar se email já existe
        result = await db.execute(select(User).where(User.email == user_data.email))
        existing_user = result.scalar_one_or_none()

        if existing_user:
            raise ValidationError(
                message="Email já cadastrado",
                details={"email": user_data.email},
            )

        # Criar hash da senha
        hashed_password = get_password_hash(user_data.password)

        # Criar usuário
        new_user = User(
            email=user_data.email,
            full_name=user_data.full_name,
            hashed_password=hashed_password,
            is_active=True,
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        return UserResponse.model_validate(new_user)

    @staticmethod
    async def authenticate_user(login_data: LoginRequest, db: AsyncSession) -> LoginResponse:
        """
        Autentica um usuário e retorna um token JWT.

        Args:
            login_data: Credenciais de login.
            db: Sessão do banco de dados.

        Returns:
            LoginResponse: Token JWT e dados do usuário.

        Raises:
            AuthenticationError: Se as credenciais forem inválidas.
        """
        # Buscar usuário por email
        result = await db.execute(select(User).where(User.email == login_data.email))
        user = result.scalar_one_or_none()

        # Verificar se usuário existe e senha está correta
        if not user or not verify_password(login_data.password, user.hashed_password):
            raise AuthenticationError(
                message="Email ou senha incorretos",
                details={"email": login_data.email},
            )

        # Verificar se usuário está ativo
        if not user.is_active:
            raise AuthenticationError(
                message="Usuário inativo",
                details={"email": login_data.email},
            )

        # Criar token JWT
        access_token = create_access_token(data={"sub": str(user.id)})

        # Retornar resposta
        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            user={
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "created_at": user.created_at.isoformat(),
            },
        )

