"""Testes para anotações."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_create_note(client: AsyncClient, db_session: AsyncSession):
    """Testa criação de anotação."""
    # Registrar e fazer login
    await client.post(
        "/auth/register",
        json={"email": "notes@test.com", "full_name": "Notes User", "password": "pass123456"},
    )
    login_response = await client.post(
        "/auth/login", json={"email": "notes@test.com", "password": "pass123456"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Criar anotação
    note_data = {
        "title": "Minha primeira anotação",
        "content": "Este é o conteúdo da anotação",
        "tags": ["medicina", "estudo"],
        "is_favorite": False,
    }
    response = await client.post("/notes/", json=note_data, headers=headers)

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == note_data["title"]
    assert data["content"] == note_data["content"]
    assert data["tags"] == note_data["tags"]
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_list_notes(client: AsyncClient, db_session: AsyncSession):
    """Testa listagem de anotações."""
    # Setup: registrar, login e criar algumas anotações
    await client.post(
        "/auth/register",
        json={"email": "list@test.com", "full_name": "List User", "password": "pass123456"},
    )
    login_response = await client.post(
        "/auth/login", json={"email": "list@test.com", "password": "pass123456"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Criar 3 anotações
    for i in range(3):
        await client.post(
            "/notes/",
            json={
                "title": f"Anotação {i+1}",
                "content": f"Conteúdo {i+1}",
                "tags": ["tag1"] if i % 2 == 0 else ["tag2"],
            },
            headers=headers,
        )

    # Listar todas
    response = await client.get("/notes/", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["notes"]) == 3
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_get_note_by_id(client: AsyncClient, db_session: AsyncSession):
    """Testa obter anotação específica."""
    # Setup
    await client.post(
        "/auth/register",
        json={"email": "get@test.com", "full_name": "Get User", "password": "pass123456"},
    )
    login_response = await client.post(
        "/auth/login", json={"email": "get@test.com", "password": "pass123456"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Criar anotação
    create_response = await client.post(
        "/notes/",
        json={"title": "Test Note", "content": "Test Content"},
        headers=headers,
    )
    note_id = create_response.json()["id"]

    # Obter anotação
    response = await client.get(f"/notes/{note_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == note_id
    assert data["title"] == "Test Note"


@pytest.mark.asyncio
async def test_update_note(client: AsyncClient, db_session: AsyncSession):
    """Testa atualização de anotação."""
    # Setup
    await client.post(
        "/auth/register",
        json={"email": "update@test.com", "full_name": "Update User", "password": "pass123456"},
    )
    login_response = await client.post(
        "/auth/login", json={"email": "update@test.com", "password": "pass123456"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Criar anotação
    create_response = await client.post(
        "/notes/",
        json={"title": "Original", "content": "Original content"},
        headers=headers,
    )
    note_id = create_response.json()["id"]

    # Atualizar
    update_data = {"title": "Updated Title", "is_favorite": True}
    response = await client.put(f"/notes/{note_id}", json=update_data, headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["is_favorite"] is True
    assert data["content"] == "Original content"  # Não alterado


@pytest.mark.asyncio
async def test_delete_note(client: AsyncClient, db_session: AsyncSession):
    """Testa deleção de anotação."""
    # Setup
    await client.post(
        "/auth/register",
        json={"email": "delete@test.com", "full_name": "Delete User", "password": "pass123456"},
    )
    login_response = await client.post(
        "/auth/login", json={"email": "delete@test.com", "password": "pass123456"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Criar anotação
    create_response = await client.post(
        "/notes/",
        json={"title": "To Delete", "content": "Will be deleted"},
        headers=headers,
    )
    note_id = create_response.json()["id"]

    # Deletar
    response = await client.delete(f"/notes/{note_id}", headers=headers)
    assert response.status_code == 204

    # Verificar que foi deletada
    get_response = await client.get(f"/notes/{note_id}", headers=headers)
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_search_notes(client: AsyncClient, db_session: AsyncSession):
    """Testa busca de anotações."""
    # Setup
    await client.post(
        "/auth/register",
        json={"email": "search@test.com", "full_name": "Search User", "password": "pass123456"},
    )
    login_response = await client.post(
        "/auth/login", json={"email": "search@test.com", "password": "pass123456"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Criar anotações
    await client.post(
        "/notes/",
        json={"title": "Python Programming", "content": "Learning Python"},
        headers=headers,
    )
    await client.post(
        "/notes/",
        json={"title": "JavaScript Basics", "content": "Learning JS"},
        headers=headers,
    )

    # Buscar por "Python"
    response = await client.get("/notes/?search=Python", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert "Python" in data["notes"][0]["title"]


@pytest.mark.asyncio
async def test_filter_by_tags(client: AsyncClient, db_session: AsyncSession):
    """Testa filtro por tags."""
    # Setup
    await client.post(
        "/auth/register",
        json={"email": "tags@test.com", "full_name": "Tags User", "password": "pass123456"},
    )
    login_response = await client.post(
        "/auth/login", json={"email": "tags@test.com", "password": "pass123456"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Criar anotações com diferentes tags
    await client.post(
        "/notes/",
        json={"title": "Note 1", "content": "Content 1", "tags": ["medicina", "cardiologia"]},
        headers=headers,
    )
    await client.post(
        "/notes/",
        json={"title": "Note 2", "content": "Content 2", "tags": ["medicina", "neurologia"]},
        headers=headers,
    )
    await client.post(
        "/notes/",
        json={"title": "Note 3", "content": "Content 3", "tags": ["farmacologia"]},
        headers=headers,
    )

    # Filtrar por tag "medicina"
    response = await client.get("/notes/?tags=medicina", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_filter_favorites(client: AsyncClient, db_session: AsyncSession):
    """Testa filtro de favoritas."""
    # Setup
    await client.post(
        "/auth/register",
        json={"email": "fav@test.com", "full_name": "Fav User", "password": "pass123456"},
    )
    login_response = await client.post(
        "/auth/login", json={"email": "fav@test.com", "password": "pass123456"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Criar anotações
    await client.post(
        "/notes/",
        json={"title": "Favorite", "content": "Content", "is_favorite": True},
        headers=headers,
    )
    await client.post(
        "/notes/",
        json={"title": "Not Favorite", "content": "Content", "is_favorite": False},
        headers=headers,
    )

    # Filtrar favoritas
    response = await client.get("/notes/?is_favorite=true", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["notes"][0]["is_favorite"] is True


@pytest.mark.asyncio
async def test_get_all_tags(client: AsyncClient, db_session: AsyncSession):
    """Testa obter todas as tags do usuário."""
    # Setup
    await client.post(
        "/auth/register",
        json={"email": "alltags@test.com", "full_name": "AllTags User", "password": "pass123456"},
    )
    login_response = await client.post(
        "/auth/login", json={"email": "alltags@test.com", "password": "pass123456"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Criar anotações com várias tags
    await client.post(
        "/notes/",
        json={"title": "Note 1", "content": "Content", "tags": ["medicina", "cardiologia"]},
        headers=headers,
    )
    await client.post(
        "/notes/",
        json={"title": "Note 2", "content": "Content", "tags": ["medicina", "neurologia"]},
        headers=headers,
    )

    # Obter todas as tags
    response = await client.get("/notes/tags", headers=headers)
    assert response.status_code == 200
    tags = response.json()
    assert len(tags) == 3
    assert "medicina" in tags
    assert "cardiologia" in tags
    assert "neurologia" in tags


@pytest.mark.asyncio
async def test_pagination(client: AsyncClient, db_session: AsyncSession):
    """Testa paginação."""
    # Setup
    await client.post(
        "/auth/register",
        json={"email": "page@test.com", "full_name": "Page User", "password": "pass123456"},
    )
    login_response = await client.post(
        "/auth/login", json={"email": "page@test.com", "password": "pass123456"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Criar 25 anotações
    for i in range(25):
        await client.post(
            "/notes/",
            json={"title": f"Note {i}", "content": f"Content {i}"},
            headers=headers,
        )

    # Primeira página (20 itens)
    response = await client.get("/notes/?page=1&page_size=20", headers=headers)
    data = response.json()
    assert data["total"] == 25
    assert len(data["notes"]) == 20
    assert data["page"] == 1
    assert data["total_pages"] == 2

    # Segunda página (5 itens)
    response = await client.get("/notes/?page=2&page_size=20", headers=headers)
    data = response.json()
    assert len(data["notes"]) == 5
    assert data["page"] == 2

