"""Rotas de RAG (Retrieval Augmented Generation)."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.rag import (
    AskQuestionRequest,
    AskQuestionResponse,
    ReindexResponse,
    SemanticSearchRequest,
    SemanticSearchResponse,
    SemanticSearchResult,
)
from app.services.rag_service import RAGService

router = APIRouter(prefix="/rag", tags=["RAG"])


@router.post(
    "/search",
    response_model=SemanticSearchResponse,
    summary="Busca semântica",
    description="Busca anotações usando embeddings e similaridade semântica.",
)
async def semantic_search(
    search_request: SemanticSearchRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SemanticSearchResponse:
    """Busca semântica nas anotações do usuário."""
    results = await RAGService.semantic_search(
        query=search_request.query,
        user_id=current_user.id,
        db=db,
        limit=search_request.limit,
        similarity_threshold=search_request.similarity_threshold,
    )

    return SemanticSearchResponse(
        query=search_request.query,
        results=[SemanticSearchResult(**result) for result in results],
        total_results=len(results),
    )


@router.post(
    "/ask",
    response_model=AskQuestionResponse,
    summary="Perguntar com RAG",
    description="Faz uma pergunta e recebe resposta gerada com contexto das anotações.",
)
async def ask_question(
    ask_request: AskQuestionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AskQuestionResponse:
    """Responde uma pergunta usando RAG."""
    response = await RAGService.ask_with_context(
        question=ask_request.question,
        user_id=current_user.id,
        db=db,
        context_limit=ask_request.context_limit,
    )

    return AskQuestionResponse(
        question=ask_request.question,
        answer=response["answer"],
        context_used=response["context_used"],
        has_context=response["has_context"],
    )


@router.post(
    "/reindex",
    response_model=ReindexResponse,
    status_code=status.HTTP_200_OK,
    summary="Reindexar anotações",
    description="Reindexa todas as anotações do usuário (regenera embeddings).",
)
async def reindex_notes(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReindexResponse:
    """Reindexa todas as anotações do usuário."""
    stats = await RAGService.reindex_all_notes(current_user.id, db)

    message = f"Reindexação completa! {stats['indexed']}/{stats['total_notes']} anotações indexadas"
    if stats["errors"] > 0:
        message += f" ({stats['errors']} erros)"

    return ReindexResponse(
        total_notes=stats["total_notes"],
        indexed=stats["indexed"],
        errors=stats["errors"],
        message=message,
    )

