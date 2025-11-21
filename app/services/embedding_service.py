"""Service para geração de embeddings."""

import google.generativeai as genai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.models.note import Note
from app.models.note_embedding import NoteEmbedding

# Configurar API do Google
genai.configure(api_key=settings.google_api_key)


class EmbeddingService:
    """Service para geração e gerenciamento de embeddings."""

    @staticmethod
    def generate_embedding(text: str) -> list[float]:
        """
        Gera embedding para um texto usando Google Gemini.

        Args:
            text: Texto para gerar embedding.

        Returns:
            list[float]: Vetor de embedding (768 dimensões).
        """
        result = genai.embed_content(
            model=settings.embedding_model,
            content=text,
            task_type="retrieval_document",
        )
        return result["embedding"]

    @staticmethod
    def generate_query_embedding(query: str) -> list[float]:
        """
        Gera embedding para uma query de busca.

        Args:
            query: Query de busca.

        Returns:
            list[float]: Vetor de embedding (768 dimensões).
        """
        result = genai.embed_content(
            model=settings.embedding_model,
            content=query,
            task_type="retrieval_query",
        )
        return result["embedding"]

    @staticmethod
    async def create_or_update_embedding(
        note: Note,
        db: AsyncSession,
    ) -> NoteEmbedding:
        """
        Cria ou atualiza embedding de uma anotação.

        Args:
            note: Anotação para gerar embedding.
            db: Sessão do banco de dados.

        Returns:
            NoteEmbedding: Embedding criado/atualizado.
        """
        # Combinar título e conteúdo para embedding
        text = f"{note.title}\n\n{note.content}"

        # Gerar embedding
        embedding_vector = EmbeddingService.generate_embedding(text)

        # Verificar se já existe embedding
        result = await db.execute(
            select(NoteEmbedding).where(NoteEmbedding.note_id == note.id)
        )
        existing_embedding = result.scalar_one_or_none()

        if existing_embedding:
            # Atualizar existente
            existing_embedding.embedding = embedding_vector
            existing_embedding.embedding_model = settings.embedding_model
            await db.commit()
            await db.refresh(existing_embedding)
            return existing_embedding
        else:
            # Criar novo
            new_embedding = NoteEmbedding(
                note_id=note.id,
                embedding=embedding_vector,
                embedding_model=settings.embedding_model,
            )
            db.add(new_embedding)
            await db.commit()
            await db.refresh(new_embedding)
            return new_embedding

    @staticmethod
    async def delete_embedding(note_id: str, db: AsyncSession) -> None:
        """
        Deleta embedding de uma anotação.

        Args:
            note_id: ID da anotação.
            db: Sessão do banco de dados.
        """
        result = await db.execute(
            select(NoteEmbedding).where(NoteEmbedding.note_id == note_id)
        )
        embedding = result.scalar_one_or_none()

        if embedding:
            await db.delete(embedding)
            await db.commit()

