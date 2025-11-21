"""Rotas para agentes LangGraph."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, Form, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import (
    CalendarOrganizerAgent,
    MedicalAssistantAgent,
    NoteAnalyzerAgent,
)
from app.config.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.agent import (
    CalendarOrganizeRequest,
    CalendarOrganizeResponse,
    MedicalAssistantRequest,
    MedicalAssistantResponse,
    MultipleNotesAnalysisRequest,
    MultipleNotesAnalysisResponse,
    NoteAnalysisRequest,
    NoteAnalysisResponse,
    WorkloadAnalysisRequest,
    WorkloadAnalysisResponse,
)
from app.services.document_generator import DocumentGenerator

router = APIRouter(prefix="/agents", tags=["Agentes"])


@router.post(
    "/medical-assistant/chat",
    response_model=MedicalAssistantResponse,
    summary="Chat com Medical Assistant",
    description="Conversa com a assistente médica usando RAG.",
)
async def chat_with_medical_assistant(
    request: MedicalAssistantRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MedicalAssistantResponse:
    """Chat com Medical Assistant."""
    from app.models.conversation import Conversation
    from app.models.message import Message
    from sqlalchemy import select

    agent = MedicalAssistantAgent()

    # Converter histórico
    history = [{"role": msg.role, "content": msg.content} for msg in request.conversation_history]

    result = await agent.chat(
        message=request.message,
        user_id=current_user.id,
        db=db,
        conversation_history=history if history else None,
    )

    # Salvar mensagens na conversa se conversation_id for fornecido
    if request.conversation_id:
        # Verificar se a conversa existe
        query = select(Conversation).where(
            Conversation.id == request.conversation_id,
            Conversation.user_id == current_user.id,
        )
        conv_result = await db.execute(query)
        conversation = conv_result.scalar_one_or_none()

        if conversation:
            # Salvar mensagem do usuário
            user_message = Message(
                conversation_id=request.conversation_id,
                role="user",
                content=request.message,
            )
            db.add(user_message)

            # Salvar resposta do assistente
            assistant_message = Message(
                conversation_id=request.conversation_id,
                role="assistant",
                content=result["response"],
            )
            db.add(assistant_message)

            await db.commit()

    return MedicalAssistantResponse(**result)


@router.post(
    "/medical-assistant/analyze-file",
    response_model=MedicalAssistantResponse,
    summary="Analisar imagem/arquivo",
    description="Analisa uma imagem ou arquivo e responde baseado no conteúdo.",
)
async def analyze_file_with_medical_assistant(
    file: UploadFile = File(...),
    question: str = Form(default="Analise este arquivo e me dê informações relevantes"),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> MedicalAssistantResponse:
    """Analisa uma imagem ou arquivo com a assistente médica."""
    print(f"[ANALYZE-FILE] Recebido arquivo: {file.filename}, tipo: {file.content_type}, pergunta: {question}")
    
    # Validar tipo de arquivo
    allowed_types = [
        "image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp",
        "application/pdf",
        "text/plain", "text/csv",
    ]
    
    if file.content_type not in allowed_types:
        from fastapi import HTTPException
        print(f"[ANALYZE-FILE] ❌ Tipo não permitido: {file.content_type}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de arquivo não suportado: {file.content_type}. Tipos permitidos: {', '.join(allowed_types)}"
        )
    
    # Ler conteúdo do arquivo
    file_content = await file.read()
    print(f"[ANALYZE-FILE] Arquivo lido: {len(file_content)} bytes")
    
    # Validar tamanho (máximo 10MB)
    max_size = 10 * 1024 * 1024  # 10MB
    if len(file_content) > max_size:
        from fastapi import HTTPException
        print(f"[ANALYZE-FILE] ❌ Arquivo muito grande: {len(file_content)} bytes")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Arquivo muito grande. Tamanho máximo: 10MB"
        )
    
    # Analisar arquivo
    print(f"[ANALYZE-FILE] Iniciando análise com MedicalAssistantAgent...")
    agent = MedicalAssistantAgent()
    try:
        result = await agent.analyze_file(
            file_content=file_content,
            file_type=file.content_type or "application/octet-stream",
            question=question,
            user_id=current_user.id,
            db=db,
        )
        print(f"[ANALYZE-FILE] ✅ Análise concluída. Resposta: {len(result.get('response', ''))} caracteres")
    except Exception as e:
        print(f"[ANALYZE-FILE] ❌ Erro na análise: {e}")
        import traceback
        traceback.print_exc()
        raise
    
    return MedicalAssistantResponse(
        response=result["response"],
        context_used=[],
        has_context=result.get("has_context", False),
        agent=result["agent"],
    )


@router.post(
    "/note-analyzer/analyze",
    response_model=NoteAnalysisResponse,
    summary="Analisar nota",
    description="Analisa uma anotação e fornece insights.",
)
async def analyze_note(
    request: NoteAnalysisRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NoteAnalysisResponse:
    """Analisa uma nota."""
    agent = NoteAnalyzerAgent()

    state = {
        "note_id": UUID(request.note_id),
        "user_id": current_user.id,
        "db": db,
    }

    result = await agent.execute(state)

    if result.get("error"):
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=result["error"])

    return NoteAnalysisResponse(
        analysis=result["analysis"],
        note_title=result["note_title"],
        agent=result["agent_used"],
    )


@router.post(
    "/note-analyzer/analyze-multiple",
    response_model=MultipleNotesAnalysisResponse,
    summary="Analisar múltiplas notas",
    description="Analisa um conjunto de notas e identifica padrões.",
)
async def analyze_multiple_notes(
    request: MultipleNotesAnalysisRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MultipleNotesAnalysisResponse:
    """Analisa múltiplas notas."""
    agent = NoteAnalyzerAgent()

    result = await agent.analyze_multiple_notes(
        user_id=current_user.id,
        db=db,
        limit=request.limit,
    )

    return MultipleNotesAnalysisResponse(**result)


@router.post(
    "/calendar-organizer/organize",
    response_model=CalendarOrganizeResponse,
    summary="Organizar calendário",
    description="Organiza calendário de plantões e turnos médicos.",
)
async def organize_calendar(
    request: CalendarOrganizeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> CalendarOrganizeResponse:
    """Organiza calendário."""
    agent = CalendarOrganizerAgent()

    state = {
        "calendar_text": request.calendar_text,
        "month": request.month,
        "year": request.year,
    }

    result = await agent.execute(state)

    return CalendarOrganizeResponse(
        organized_calendar=result["organized_calendar"],
        agent=result["agent_used"],
    )


@router.post(
    "/calendar-organizer/workload",
    response_model=WorkloadAnalysisResponse,
    summary="Analisar carga de trabalho",
    description="Analisa carga de trabalho e identifica sobrecarga.",
)
async def analyze_workload(
    request: WorkloadAnalysisRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> WorkloadAnalysisResponse:
    """Analisa carga de trabalho."""
    agent = CalendarOrganizerAgent()

    result = await agent.analyze_workload(
        calendar_text=request.calendar_text,
        period_days=request.period_days,
    )

    return WorkloadAnalysisResponse(**result)


@router.post(
    "/generate-document",
    summary="Gerar documento estruturado",
    description="Gera um arquivo Excel ou Word a partir de uma resposta da IA.",
)
async def generate_document(
    text: str = Form(..., description="Texto da resposta da IA (Markdown ou texto simples)"),
    format: str = Form(default="excel", description="Formato: 'excel' ou 'word'"),
    filename: str = Form(default="resposta_ia", description="Nome do arquivo (sem extensão)"),
    current_user: Annotated[User, Depends(get_current_user)] = None,
) -> StreamingResponse:
    """
    Gera um documento estruturado (Excel ou Word) a partir de uma resposta da IA.
    
    Args:
        text: Texto da resposta da IA
        format: Formato do documento ("excel" ou "word")
        filename: Nome do arquivo (sem extensão)
        current_user: Usuário autenticado
    
    Returns:
        StreamingResponse com o arquivo gerado
    """
    try:
        # Validar formato
        if format.lower() not in ["excel", "word", "xlsx", "docx"]:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato não suportado. Use 'excel' ou 'word'."
            )
        
        # Normalizar formato
        if format.lower() in ["excel", "xlsx"]:
            file_format = "excel"
            extension = "xlsx"
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            file_format = "word"
            extension = "docx"
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        
        # Gerar documento
        document_bytes = DocumentGenerator.generate_from_ai_response(
            ai_response=text,
            format=file_format,
            filename=filename,
        )
        
        # Retornar como streaming response
        return StreamingResponse(
            iter([document_bytes.read()]),
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}.{extension}"',
            },
        )
    except Exception as e:
        from fastapi import HTTPException
        print(f"❌ Erro ao gerar documento: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao gerar documento: {str(e)}"
        )

