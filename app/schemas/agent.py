"""Schemas Pydantic para Agents."""

from uuid import UUID

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Mensagem de chat."""

    role: str = Field(..., description="Papel (user ou assistant)")
    content: str = Field(..., description="Conteúdo da mensagem")


class MedicalAssistantRequest(BaseModel):
    """Request para Medical Assistant."""

    message: str = Field(..., min_length=1, description="Mensagem/pergunta do usuário")
    conversation_id: UUID | None = Field(None, description="ID da conversa (opcional)")
    conversation_history: list[ChatMessage] = Field(
        default_factory=list, description="Histórico da conversa"
    )


class MedicalAssistantResponse(BaseModel):
    """Response do Medical Assistant."""

    response: str = Field(..., description="Resposta do assistente")
    context_used: list[dict] = Field(..., description="Contexto usado")
    has_context: bool = Field(..., description="Se encontrou contexto relevante")
    agent: str = Field(..., description="Nome do agente")


class NoteAnalysisRequest(BaseModel):
    """Request para análise de nota."""

    note_id: str = Field(..., description="ID da nota para analisar")


class NoteAnalysisResponse(BaseModel):
    """Response da análise de nota."""

    analysis: str = Field(..., description="Análise da nota")
    note_title: str = Field(..., description="Título da nota analisada")
    agent: str = Field(..., description="Nome do agente")


class MultipleNotesAnalysisRequest(BaseModel):
    """Request para análise de múltiplas notas."""

    limit: int = Field(default=10, ge=1, le=50, description="Número de notas a analisar")


class MultipleNotesAnalysisResponse(BaseModel):
    """Response da análise de múltiplas notas."""

    summary: str = Field(..., description="Resumo da análise")
    total_notes_analyzed: int = Field(..., description="Total de notas analisadas")
    agent: str = Field(..., description="Nome do agente")


class CalendarOrganizeRequest(BaseModel):
    """Request para organizar calendário."""

    calendar_text: str = Field(..., min_length=1, description="Texto do calendário")
    month: int | None = Field(None, ge=1, le=12, description="Mês de referência")
    year: int | None = Field(None, ge=2020, le=2030, description="Ano de referência")


class CalendarOrganizeResponse(BaseModel):
    """Response da organização de calendário."""

    organized_calendar: str = Field(..., description="Calendário organizado")
    agent: str = Field(..., description="Nome do agente")


class WorkloadAnalysisRequest(BaseModel):
    """Request para análise de carga de trabalho."""

    calendar_text: str = Field(..., min_length=1, description="Texto do calendário")
    period_days: int = Field(default=30, ge=7, le=90, description="Dias do período")


class WorkloadAnalysisResponse(BaseModel):
    """Response da análise de carga."""

    analysis: str = Field(..., description="Análise de carga de trabalho")
    period_days: int = Field(..., description="Dias analisados")
    agent: str = Field(..., description="Nome do agente")

