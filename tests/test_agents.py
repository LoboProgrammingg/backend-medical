"""Testes para agentes LangGraph."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_medical_assistant_chat(client: AsyncClient, db_session: AsyncSession):
    """Testa chat com Medical Assistant."""
    # Setup: registrar, login e criar nota
    await client.post(
        "/auth/register",
        json={"email": "agent@test.com", "full_name": "Agent User", "password": "pass123456"},
    )
    login_response = await client.post(
        "/auth/login", json={"email": "agent@test.com", "password": "pass123456"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Criar uma nota
    with patch("app.services.embedding_service.EmbeddingService.generate_embedding") as mock_embed:
        mock_embed.return_value = [0.1] * 768
        await client.post(
            "/notes/",
            json={"title": "Farmacologia", "content": "Antibióticos beta-lactâmicos..."},
            headers=headers,
        )

    # Mock das funções de embeddings e LLM
    with patch("app.services.embedding_service.EmbeddingService.generate_query_embedding") as mock_query, \
         patch("app.agents.base_agent.BaseAgent.generate_response") as mock_llm:
        
        mock_query.return_value = [0.1] * 768
        mock_llm.return_value = "Com base nas suas anotações sobre antibióticos..."

        response = await client.post(
            "/agents/medical-assistant/chat",
            json={"message": "O que são antibióticos?"},
            headers=headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "agent" in data
    assert data["agent"] == "Medical Assistant"


@pytest.mark.asyncio
async def test_note_analyzer(client: AsyncClient, db_session: AsyncSession):
    """Testa análise de nota."""
    # Setup
    await client.post(
        "/auth/register",
        json={"email": "analyzer@test.com", "full_name": "Analyzer User", "password": "pass123456"},
    )
    login_response = await client.post(
        "/auth/login", json={"email": "analyzer@test.com", "password": "pass123456"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Criar nota
    with patch("app.services.embedding_service.EmbeddingService.generate_embedding") as mock_embed:
        mock_embed.return_value = [0.1] * 768
        note_response = await client.post(
            "/notes/",
            json={"title": "Cardiologia", "content": "ICC - Insuficiência Cardíaca..."},
            headers=headers,
        )
    
    note_id = note_response.json()["id"]

    # Analisar nota
    with patch("app.agents.base_agent.BaseAgent.generate_response") as mock_llm:
        mock_llm.return_value = "📊 ANÁLISE DA ANOTAÇÃO: Cardiologia\n\n✅ Pontos Fortes..."
        
        response = await client.post(
            "/agents/note-analyzer/analyze",
            json={"note_id": note_id},
            headers=headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert "analysis" in data
    assert "note_title" in data
    assert data["note_title"] == "Cardiologia"
    assert data["agent"] == "Note Analyzer"


@pytest.mark.asyncio
async def test_analyze_multiple_notes(client: AsyncClient, db_session: AsyncSession):
    """Testa análise de múltiplas notas."""
    # Setup
    await client.post(
        "/auth/register",
        json={"email": "multi@test.com", "full_name": "Multi User", "password": "pass123456"},
    )
    login_response = await client.post(
        "/auth/login", json={"email": "multi@test.com", "password": "pass123456"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Criar algumas notas
    with patch("app.services.embedding_service.EmbeddingService.generate_embedding") as mock_embed:
        mock_embed.return_value = [0.1] * 768
        for i in range(3):
            await client.post(
                "/notes/",
                json={"title": f"Nota {i+1}", "content": f"Conteúdo {i+1}"},
                headers=headers,
            )

    # Analisar múltiplas
    with patch("app.agents.base_agent.BaseAgent.generate_response") as mock_llm:
        mock_llm.return_value = "📊 Visão Geral: O estudante está focando em..."
        
        response = await client.post(
            "/agents/note-analyzer/analyze-multiple",
            json={"limit": 5},
            headers=headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "total_notes_analyzed" in data
    assert data["total_notes_analyzed"] == 3


@pytest.mark.asyncio
async def test_calendar_organizer(client: AsyncClient, db_session: AsyncSession):
    """Testa organização de calendário."""
    # Setup
    await client.post(
        "/auth/register",
        json={"email": "calendar@test.com", "full_name": "Calendar User", "password": "pass123456"},
    )
    login_response = await client.post(
        "/auth/login", json={"email": "calendar@test.com", "password": "pass123456"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    calendar_text = """
    Segunda: Plantão 24h
    Terça: Folga
    Quarta: Turno regular 8-17h
    Quinta: Plantão noturno
    Sexta: Folga
    """

    with patch("app.agents.base_agent.BaseAgent.generate_response") as mock_llm:
        mock_llm.return_value = "📅 CALENDÁRIO ORGANIZADO\n\n🏥 Segunda: Plantão 24h..."
        
        response = await client.post(
            "/agents/calendar-organizer/organize",
            json={"calendar_text": calendar_text, "month": 11, "year": 2025},
            headers=headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert "organized_calendar" in data
    assert data["agent"] == "Calendar Organizer"


@pytest.mark.asyncio
async def test_workload_analysis(client: AsyncClient, db_session: AsyncSession):
    """Testa análise de carga de trabalho."""
    # Setup
    await client.post(
        "/auth/register",
        json={"email": "workload@test.com", "full_name": "Workload User", "password": "pass123456"},
    )
    login_response = await client.post(
        "/auth/login", json={"email": "workload@test.com", "password": "pass123456"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    calendar_text = "Plantões: 3x semana, Turnos: 2x semana"

    with patch("app.agents.base_agent.BaseAgent.generate_response") as mock_llm:
        mock_llm.return_value = "📊 ANÁLISE DE CARGA\n\n• Total horas: 48h/semana..."
        
        response = await client.post(
            "/agents/calendar-organizer/workload",
            json={"calendar_text": calendar_text, "period_days": 30},
            headers=headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert "analysis" in data
    assert data["period_days"] == 30


@pytest.mark.asyncio
async def test_agents_require_authentication(client: AsyncClient):
    """Testa que endpoints de agents requerem autenticação."""
    # Medical Assistant sem auth
    response = await client.post(
        "/agents/medical-assistant/chat",
        json={"message": "test"},
    )
    assert response.status_code in [401, 403]

    # Note Analyzer sem auth
    response = await client.post(
        "/agents/note-analyzer/analyze",
        json={"note_id": "uuid"},
    )
    assert response.status_code in [401, 403]

    # Calendar Organizer sem auth
    response = await client.post(
        "/agents/calendar-organizer/organize",
        json={"calendar_text": "test"},
    )
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_medical_assistant_validation(client: AsyncClient, db_session: AsyncSession):
    """Testa validação do Medical Assistant."""
    await client.post(
        "/auth/register",
        json={"email": "valid@test.com", "full_name": "Valid User", "password": "pass123456"},
    )
    login_response = await client.post(
        "/auth/login", json={"email": "valid@test.com", "password": "pass123456"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Mensagem vazia
    response = await client.post(
        "/agents/medical-assistant/chat",
        json={"message": ""},
        headers=headers,
    )
    assert response.status_code == 422  # Validation error

