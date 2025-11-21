"""Schemas Pydantic para RAG."""

from pydantic import BaseModel, Field


class SemanticSearchRequest(BaseModel):
    """Schema para busca semântica."""

    query: str = Field(..., min_length=1, description="Query de busca")
    limit: int = Field(default=5, ge=1, le=20, description="Número de resultados")
    similarity_threshold: float = Field(
        default=0.3, ge=0.0, le=1.0, description="Limiar de similaridade"
    )


class SemanticSearchResult(BaseModel):
    """Schema de resultado da busca semântica."""

    id: str
    title: str
    content: str
    tags: list[str]
    is_favorite: bool
    created_at: str
    updated_at: str
    similarity: float


class SemanticSearchResponse(BaseModel):
    """Schema de resposta da busca semântica."""

    query: str
    results: list[SemanticSearchResult]
    total_results: int


class AskQuestionRequest(BaseModel):
    """Schema para pergunta com RAG."""

    question: str = Field(..., min_length=1, description="Pergunta do usuário")
    context_limit: int = Field(
        default=3, ge=1, le=10, description="Número de anotações para contexto"
    )


class ContextNote(BaseModel):
    """Schema de anotação usada como contexto."""

    id: str
    title: str
    similarity: float


class AskQuestionResponse(BaseModel):
    """Schema de resposta da pergunta."""

    question: str
    answer: str
    context_used: list[ContextNote]
    has_context: bool


class ReindexResponse(BaseModel):
    """Schema de resposta da reindexação."""

    total_notes: int
    indexed: int
    errors: int
    message: str

