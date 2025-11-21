"""Testes para autenticação."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.models.user import User


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient, db_session: AsyncSession):
    """Testa registro de novo usuário."""
    user_data = {
        "email": "test@example.com",
        "full_name": "Test User",
        "password": "testpassword123",
    }

    response = await client.post("/auth/register", json=user_data)

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == user_data["email"]
    assert data["full_name"] == user_data["full_name"]
    assert "id" in data
    assert "password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, db_session: AsyncSession):
    """Testa registro com email duplicado."""
    # Criar primeiro usuário
    user_data = {
        "email": "duplicate@example.com",
        "full_name": "First User",
        "password": "password123",
    }
    await client.post("/auth/register", json=user_data)

    # Tentar criar segundo usuário com mesmo email
    user_data2 = {
        "email": "duplicate@example.com",
        "full_name": "Second User",
        "password": "password456",
    }
    response = await client.post("/auth/register", json=user_data2)

    assert response.status_code == 422
    assert "email já cadastrado" in response.json()["error"].lower()


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, db_session: AsyncSession):
    """Testa login com credenciais válidas."""
    # Registrar usuário
    user_data = {
        "email": "login@example.com",
        "full_name": "Login Test",
        "password": "password123",
    }
    await client.post("/auth/register", json=user_data)

    # Fazer login
    login_data = {"email": "login@example.com", "password": "password123"}
    response = await client.post("/auth/login", json=login_data)

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "user" in data
    assert data["user"]["email"] == user_data["email"]


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, db_session: AsyncSession):
    """Testa login com senha incorreta."""
    # Registrar usuário
    user_data = {
        "email": "wrongpass@example.com",
        "full_name": "Wrong Pass Test",
        "password": "correctpassword",
    }
    await client.post("/auth/register", json=user_data)

    # Tentar login com senha errada
    login_data = {"email": "wrongpass@example.com", "password": "wrongpassword"}
    response = await client.post("/auth/login", json=login_data)

    assert response.status_code == 401
    assert "incorretos" in response.json()["error"].lower()


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    """Testa login com usuário inexistente."""
    login_data = {"email": "nonexistent@example.com", "password": "password123"}
    response = await client.post("/auth/login", json=login_data)

    assert response.status_code == 401
    assert "incorretos" in response.json()["error"].lower()


@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient, db_session: AsyncSession):
    """Testa endpoint /auth/me com usuário autenticado."""
    # Registrar e fazer login
    user_data = {
        "email": "getme@example.com",
        "full_name": "Get Me Test",
        "password": "password123",
    }
    await client.post("/auth/register", json=user_data)

    login_response = await client.post(
        "/auth/login", json={"email": user_data["email"], "password": user_data["password"]}
    )
    token = login_response.json()["access_token"]

    # Acessar /auth/me
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == user_data["email"]
    assert data["full_name"] == user_data["full_name"]


@pytest.mark.asyncio
async def test_get_me_without_token(client: AsyncClient):
    """Testa endpoint /auth/me sem token."""
    response = await client.get("/auth/me")

    assert response.status_code == 403  # Forbidden sem Authorization header


@pytest.mark.asyncio
async def test_get_me_invalid_token(client: AsyncClient):
    """Testa endpoint /auth/me com token inválido."""
    response = await client.get("/auth/me", headers={"Authorization": "Bearer invalid_token"})

    assert response.status_code == 401

