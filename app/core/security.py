"""Funções de segurança: hash de senha e JWT."""

from datetime import datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.config.settings import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica se a senha plain text corresponde ao hash.

    Args:
        plain_password: Senha em texto plano.
        hashed_password: Hash da senha armazenado.

    Returns:
        bool: True se a senha corresponde, False caso contrário.
    """
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


def get_password_hash(password: str) -> str:
    """
    Gera hash de uma senha usando bcrypt.

    Args:
        password: Senha em texto plano.

    Returns:
        str: Hash da senha.
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """
    Cria um token JWT de acesso.

    Args:
        data: Dados a serem codificados no token.
        expires_delta: Tempo de expiração customizado (opcional).

    Returns:
        str: Token JWT codificado.
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)

    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any] | None:
    """
    Decodifica e valida um token JWT.

    Args:
        token: Token JWT a ser decodificado.

    Returns:
        dict | None: Payload do token se válido, None caso contrário.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        return None

