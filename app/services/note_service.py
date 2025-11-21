"""Service layer para anotações."""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.note import Note
from app.schemas.note import NoteCreate, NoteListResponse, NoteResponse, NoteUpdate
from app.services.embedding_service import EmbeddingService
from app.utils.errors import NotFoundError, ValidationError


class NoteService:
    """Service para operações com anotações."""

    @staticmethod
    async def create_note(
        note_data: NoteCreate,
        user_id: UUID,
        db: AsyncSession,
    ) -> NoteResponse:
        """
        Cria uma nova anotação.

        Args:
            note_data: Dados da anotação.
            user_id: ID do usuário proprietário.
            db: Sessão do banco de dados.

        Returns:
            NoteResponse: Anotação criada.
        """
        new_note = Note(
            user_id=user_id,
            title=note_data.title,
            content=note_data.content,
            tags=note_data.tags,
            is_favorite=note_data.is_favorite,
        )

        db.add(new_note)
        await db.commit()
        await db.refresh(new_note)

        # Indexar automaticamente (gerar embedding)
        try:
            await EmbeddingService.create_or_update_embedding(new_note, db)
        except Exception as e:
            # Log do erro, mas não falha a operação
            print(f"Aviso: Erro ao indexar nota {new_note.id}: {e}")

        return NoteResponse.model_validate(new_note)

    @staticmethod
    async def get_user_notes(
        user_id: UUID,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        tags: list[str] | None = None,
        is_favorite: bool | None = None,
    ) -> NoteListResponse:
        """
        Lista anotações do usuário com filtros e paginação.

        Args:
            user_id: ID do usuário.
            db: Sessão do banco de dados.
            page: Número da página.
            page_size: Tamanho da página.
            search: Termo de busca (título ou conteúdo).
            tags: Filtrar por tags.
            is_favorite: Filtrar favoritas.

        Returns:
            NoteListResponse: Lista paginada de anotações.
        """
        # Query base
        query = select(Note).where(Note.user_id == user_id)

        # Aplicar filtros
        if search:
            search_filter = or_(
                Note.title.ilike(f"%{search}%"),
                Note.content.ilike(f"%{search}%"),
            )
            query = query.where(search_filter)

        if tags:
            # Filtrar por qualquer tag da lista
            for tag in tags:
                query = query.where(Note.tags.contains([tag]))

        if is_favorite is not None:
            query = query.where(Note.is_favorite == is_favorite)

        # Ordenar por data de atualização (mais recentes primeiro)
        query = query.order_by(Note.updated_at.desc())

        # Contar total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Aplicar paginação
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # Executar query
        result = await db.execute(query)
        notes = result.scalars().all()

        # Calcular total de páginas
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0

        return NoteListResponse(
            notes=[NoteResponse.model_validate(note) for note in notes],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    @staticmethod
    async def get_note_by_id(
        note_id: UUID,
        user_id: UUID,
        db: AsyncSession,
    ) -> NoteResponse:
        """
        Obtém uma anotação específica.

        Args:
            note_id: ID da anotação.
            user_id: ID do usuário (para verificar propriedade).
            db: Sessão do banco de dados.

        Returns:
            NoteResponse: Anotação encontrada.

        Raises:
            NotFoundError: Se a anotação não existir ou não pertencer ao usuário.
        """
        result = await db.execute(
            select(Note).where(Note.id == note_id, Note.user_id == user_id)
        )
        note = result.scalar_one_or_none()

        if not note:
            raise NotFoundError(resource="Anotação")

        return NoteResponse.model_validate(note)

    @staticmethod
    async def update_note(
        note_id: UUID,
        note_data: NoteUpdate,
        user_id: UUID,
        db: AsyncSession,
    ) -> NoteResponse:
        """
        Atualiza uma anotação.

        Args:
            note_id: ID da anotação.
            note_data: Dados para atualizar.
            user_id: ID do usuário (para verificar propriedade).
            db: Sessão do banco de dados.

        Returns:
            NoteResponse: Anotação atualizada.

        Raises:
            NotFoundError: Se a anotação não existir ou não pertencer ao usuário.
        """
        result = await db.execute(
            select(Note).where(Note.id == note_id, Note.user_id == user_id)
        )
        note = result.scalar_one_or_none()

        if not note:
            raise NotFoundError(resource="Anotação")

        # Atualizar apenas campos fornecidos
        update_data = note_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(note, field, value)

        await db.commit()
        await db.refresh(note)

        # Reindexar se título ou conteúdo mudaram
        if "title" in update_data or "content" in update_data:
            try:
                await EmbeddingService.create_or_update_embedding(note, db)
            except Exception as e:
                print(f"Aviso: Erro ao reindexar nota {note.id}: {e}")

        return NoteResponse.model_validate(note)

    @staticmethod
    async def delete_note(
        note_id: UUID,
        user_id: UUID,
        db: AsyncSession,
    ) -> None:
        """
        Deleta uma anotação.

        Args:
            note_id: ID da anotação.
            user_id: ID do usuário (para verificar propriedade).
            db: Sessão do banco de dados.

        Raises:
            NotFoundError: Se a anotação não existir ou não pertencer ao usuário.
        """
        result = await db.execute(
            select(Note).where(Note.id == note_id, Note.user_id == user_id)
        )
        note = result.scalar_one_or_none()

        if not note:
            raise NotFoundError(resource="Anotação")

        await db.delete(note)
        await db.commit()

    @staticmethod
    async def get_all_tags(user_id: UUID, db: AsyncSession) -> list[str]:
        """
        Obtém todas as tags únicas do usuário.

        Args:
            user_id: ID do usuário.
            db: Sessão do banco de dados.

        Returns:
            list[str]: Lista de tags únicas.
        """
        result = await db.execute(
            select(Note.tags).where(Note.user_id == user_id)
        )
        all_tags_lists = result.scalars().all()

        # Flatten e remover duplicatas
        unique_tags = set()
        for tags_list in all_tags_lists:
            if tags_list:
                unique_tags.update(tags_list)

        return sorted(list(unique_tags))

