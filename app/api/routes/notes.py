"""Rotas de anotações."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.note import NoteCreate, NoteListResponse, NoteResponse, NoteUpdate
from app.services.note_service import NoteService

router = APIRouter(prefix="/notes", tags=["Anotações"])


@router.post(
    "/",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar nova anotação",
    description="Cria uma nova anotação para o usuário autenticado.",
)
async def create_note(
    note_data: NoteCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NoteResponse:
    """Cria uma nova anotação."""
    return await NoteService.create_note(note_data, current_user.id, db)


@router.get(
    "/",
    response_model=NoteListResponse,
    summary="Listar anotações",
    description="Lista todas as anotações do usuário com filtros e paginação.",
)
async def list_notes(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1, description="Número da página"),
    page_size: int = Query(20, ge=1, le=100, description="Tamanho da página"),
    search: str | None = Query(None, description="Buscar em título ou conteúdo"),
    tags: list[str] | None = Query(None, description="Filtrar por tags"),
    is_favorite: bool | None = Query(None, description="Filtrar favoritas"),
) -> NoteListResponse:
    """Lista anotações do usuário."""
    return await NoteService.get_user_notes(
        user_id=current_user.id,
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        tags=tags,
        is_favorite=is_favorite,
    )


@router.get(
    "/tags",
    response_model=list[str],
    summary="Listar tags",
    description="Lista todas as tags únicas do usuário.",
)
async def list_tags(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[str]:
    """Lista todas as tags do usuário."""
    return await NoteService.get_all_tags(current_user.id, db)


@router.get(
    "/{note_id}",
    response_model=NoteResponse,
    summary="Obter anotação",
    description="Obtém uma anotação específica do usuário.",
)
async def get_note(
    note_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NoteResponse:
    """Obtém uma anotação específica."""
    return await NoteService.get_note_by_id(note_id, current_user.id, db)


@router.put(
    "/{note_id}",
    response_model=NoteResponse,
    summary="Atualizar anotação",
    description="Atualiza uma anotação existente.",
)
async def update_note(
    note_id: UUID,
    note_data: NoteUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NoteResponse:
    """Atualiza uma anotação."""
    return await NoteService.update_note(note_id, note_data, current_user.id, db)


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_200_OK,
    summary="Deletar anotação",
    description="Deleta uma anotação existente.",
)
async def delete_note(
    note_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Deleta uma anotação."""
    await NoteService.delete_note(note_id, current_user.id, db)
    return {"message": "Anotação deletada com sucesso"}

