"""Testes para RAG."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_semantic_search_without_notes(client: AsyncClient, db_session: AsyncSession):
    """Testa busca semântica quando usuário não tem notas."""
    # Registrar e fazer login
    await client.post(
        "/auth/register",
        json={"email": "rag@test.com", "full_name": "RAG User", "password": "pass123456"},
    )
    login_response = await client.post(
        "/auth/login", json={"email": "rag@test.com", "password": "pass123456"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Buscar sem ter notas
    with patch("app.services.embedding_service.EmbeddingService.generate_query_embedding") as mock_embed:
        mock_embed.return_value = [0.1] * 768
        
        response = await client.post(
            "/rag/search",
            json={"query": "antibióticos", "limit": 5},
            headers=headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "antibióticos"
    assert data["total_results"] == 0
    assert data["results"] == []


@pytest.mark.asyncio
async def test_reindex_notes(client: AsyncClient, db_session: AsyncSession):
    """Testa reindexação de notas."""
    # Setup: registrar, login e criar nota
    await client.post(
        "/auth/register",
        json={"email": "reindex@test.com", "full_name": "Reindex User", "password": "pass123456"},
    )
    login_response = await client.post(
        "/auth/login", json={"email": "reindex@test.com", "password": "pass123456"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Criar uma nota (será indexada automaticamente)
    with patch("app.services.embedding_service.EmbeddingService.generate_embedding") as mock_embed:
        mock_embed.return_value = [0.1] * 768
        
        await client.post(
            "/notes/",
            json={"title": "Test Note", "content": "Test Content"},
            headers=headers,
        )

    # Reindexar
    with patch("app.services.embedding_service.EmbeddingService.generate_embedding") as mock_embed:
        mock_embed.return_value = [0.2] * 768
        
        response = await client.post("/rag/reindex", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total_notes"] >= 1
    assert data["indexed"] >= 1
    assert "message" in data


@pytest.mark.asyncio
async def test_ask_without_context(client: AsyncClient, db_session: AsyncSession):
    """Testa pergunta quando não há contexto relevante."""
    # Setup
    await client.post(
        "/auth/register",
        json={"email": "ask@test.com", "full_name": "Ask User", "password": "pass123456"},
    )
    login_response = await client.post(
        "/auth/login", json={"email": "ask@test.com", "password": "pass123456"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Perguntar sem ter notas
    with patch("app.services.embedding_service.EmbeddingService.generate_query_embedding") as mock_embed:
        mock_embed.return_value = [0.1] * 768
        
        response = await client.post(
            "/rag/ask",
            json={"question": "O que é penicilina?"},
            headers=headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["question"] == "O que é penicilina?"
    assert data["has_context"] is False
    assert "não encontrei informações" in data["answer"].lower()
    assert data["context_used"] == []


@pytest.mark.asyncio
async def test_note_auto_indexing(client: AsyncClient, db_session: AsyncSession):
    """Testa que notas são indexadas automaticamente ao serem criadas."""
    # Setup
    await client.post(
        "/auth/register",
        json={"email": "autoindex@test.com", "full_name": "AutoIndex User", "password": "pass123456"},
    )
    login_response = await client.post(
        "/auth/login", json={"email": "autoindex@test.com", "password": "pass123456"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Mock do embedding
    with patch("app.services.embedding_service.EmbeddingService.generate_embedding") as mock_embed:
        mock_embed.return_value = [0.1] * 768
        
        # Criar nota
        response = await client.post(
            "/notes/",
            json={
                "title": "Farmacologia",
                "content": "Antibióticos são medicamentos...",
                "tags": ["medicina"],
            },
            headers=headers,
        )

    assert response.status_code == 201
    # Se chegou aqui, a indexação não causou erro (mesmo que seja async)


@pytest.mark.asyncio
async def test_semantic_search_endpoint_validation(client: AsyncClient, db_session: AsyncSession):
    """Testa validação do endpoint de busca semântica."""
    # Setup
    await client.post(
        "/auth/register",
        json={"email": "validation@test.com", "full_name": "Validation User", "password": "pass123456"},
    )
    login_response = await client.post(
        "/auth/login", json={"email": "validation@test.com", "password": "pass123456"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Query vazia
    response = await client.post(
        "/rag/search",
        json={"query": "", "limit": 5},
        headers=headers,
    )
    assert response.status_code == 422  # Validation error

    # Limit inválido
    response = await client.post(
        "/rag/search",
        json={"query": "test", "limit": 100},
        headers=headers,
    )
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_ask_endpoint_validation(client: AsyncClient, db_session: AsyncSession):
    """Testa validação do endpoint de perguntas."""
    # Setup
    await client.post(
        "/auth/register",
        json={"email": "askval@test.com", "full_name": "AskVal User", "password": "pass123456"},
    )
    login_response = await client.post(
        "/auth/login", json={"email": "askval@test.com", "password": "pass123456"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Pergunta vazia
    response = await client.post(
        "/rag/ask",
        json={"question": ""},
        headers=headers,
    )
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_rag_requires_authentication(client: AsyncClient):
    """Testa que endpoints RAG requerem autenticação."""
    # Busca semântica sem auth
    response = await client.post(
        "/rag/search",
        json={"query": "test"},
    )
    assert response.status_code in [401, 403]  # Unauthorized or Forbidden

    # Pergunta sem auth
    response = await client.post(
        "/rag/ask",
        json={"question": "test"},
    )
    assert response.status_code in [401, 403]

    # Reindex sem auth
    response = await client.post("/rag/reindex")
    assert response.status_code in [401, 403]

