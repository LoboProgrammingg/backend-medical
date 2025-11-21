"""Rotas para processamento de documentos."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.config.settings import settings
from app.core.dependencies import get_current_user
from app.models.user import User
from app.utils.pdf_processor import PDFProcessor

router = APIRouter(prefix="/documents", tags=["Documentos"])


class ProcessDirectoryRequest(BaseModel):
    """Schema para processar diretório."""

    directory_path: str
    tag: str = "documento_importado"
    pattern: str = "*.pdf"


class ProcessDirectoryResponse(BaseModel):
    """Schema de resposta do processamento."""

    total_files: int
    total_notes: int
    errors: list
    success_rate: float
    message: str


class UploadResponse(BaseModel):
    """Schema de resposta do upload."""

    filename: str
    note_id: str
    message: str
    success: bool


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload de PDF",
    description="Faz upload de um PDF e cria uma anotação automaticamente.",
)
async def upload_pdf(
    file: UploadFile = File(...),
    tag: str = "documento_medico",
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> UploadResponse:
    """Faz upload de um PDF e processa."""
    print(f"[UPLOAD] Iniciando upload de: {file.filename}")
    
    # Validar tipo de arquivo
    if not file.filename.lower().endswith(".pdf"):
        print(f"[UPLOAD] Arquivo rejeitado (não é PDF): {file.filename}")
        return UploadResponse(
            filename=file.filename,
            note_id="",
            message="Apenas arquivos PDF são permitidos",
            success=False,
        )

    # Criar diretório temporário se não existir
    temp_dir = Path(settings.storage_path) / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    print(f"[UPLOAD] Diretório temp criado: {temp_dir}")

    # Salvar arquivo temporariamente
    file_path = temp_dir / file.filename
    try:
        print(f"[UPLOAD] Lendo conteúdo do arquivo...")
        content = await file.read()
        print(f"[UPLOAD] Tamanho do arquivo: {len(content)} bytes")
        
        print(f"[UPLOAD] Salvando em: {file_path}")
        with open(file_path, "wb") as f:
            f.write(content)

        print(f"[UPLOAD] Processando PDF como documento RAG...")
        # Processar o PDF como Document (não cria anotação)
        document = await PDFProcessor.process_pdf_as_document(
            pdf_path=file_path,
            user=current_user,
            db=db,
            description=f"Documento PDF: {file.filename}",
        )

        if document:
            print(f"[UPLOAD] Sucesso! Document ID: {document.id}")
            return UploadResponse(
                filename=file.filename,
                note_id=str(document.id),  # Compatibilidade
                message=f"PDF '{file.filename}' adicionado ao RAG com sucesso!",
                success=True,
            )
        else:
            print(f"[UPLOAD] Erro: process_pdf_as_document retornou None")
            return UploadResponse(
                filename=file.filename,
                note_id="",
                message=f"Erro ao processar '{file.filename}'",
                success=False,
            )
    except Exception as e:
        print(f"[UPLOAD] Erro exception: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return UploadResponse(
            filename=file.filename,
            note_id="",
            message=f"Erro: {str(e)}",
            success=False,
        )
    finally:
        # Remover arquivo temporário
        if file_path.exists():
            print(f"[UPLOAD] Removendo arquivo temporário: {file_path}")
            file_path.unlink()


@router.post(
    "/process-directory",
    response_model=ProcessDirectoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Processar diretório de PDFs",
    description="Processa todos os PDFs de um diretório e cria anotações automaticamente.",
)
async def process_directory(
    request: ProcessDirectoryRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProcessDirectoryResponse:
    """Processa PDFs de um diretório."""
    directory_path = Path(request.directory_path)

    if not directory_path.exists():
        return ProcessDirectoryResponse(
            total_files=0,
            total_notes=0,
            errors=[{"error": f"Diretório não encontrado: {request.directory_path}"}],
            success_rate=0.0,
            message="Erro: Diretório não encontrado",
        )

    stats = await PDFProcessor.process_directory(
        directory_path=directory_path,
        user=current_user,
        db=db,
        tag=request.tag,
        pattern=request.pattern,
    )

    message = f"Processados {stats['total_files']} arquivos, {stats['total_notes']} anotações criadas"
    if stats["errors"]:
        message += f" ({len(stats['errors'])} erros)"

    return ProcessDirectoryResponse(
        total_files=stats["total_files"],
        total_notes=stats["total_notes"],
        errors=stats["errors"],
        success_rate=stats["success_rate"],
        message=message,
    )
