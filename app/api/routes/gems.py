"""Rotas para Gems (IAs Especializadas)."""

import asyncio
import shutil
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.database import get_db
from app.core.dependencies import get_current_user
from app.models.gem import Gem, GemDocument
from app.models.user import User
from app.schemas.gem import (
    GemChatRequest,
    GemChatResponse,
    GemCreate,
    GemDocumentResponse,
    GemListResponse,
    GemResponse,
    GemUpdate,
)
from app.agents.gem_agent import GemAgent
from app.services.gem_rag_service import GemRAGService

router = APIRouter(prefix="/gems", tags=["Gems"])

# Diretório para armazenar PDFs das Gems
GEMS_STORAGE = Path("storage/gems")


@router.post(
    "/",
    response_model=GemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar Gem",
    description="Cria uma nova Gem (IA especializada).",
)
async def create_gem(
    gem_data: GemCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GemResponse:
    """Cria uma nova Gem."""
    gem = Gem(
        user_id=current_user.id,
        name=gem_data.name,
        description=gem_data.description,
        instructions=gem_data.instructions,
    )
    db.add(gem)
    await db.commit()
    await db.refresh(gem)
    
    return GemResponse(
        id=gem.id,
        name=gem.name,
        description=gem.description,
        instructions=gem.instructions,
        documents=[],
        created_at=gem.created_at.isoformat(),
        updated_at=gem.updated_at.isoformat(),
    )


@router.get(
    "/",
    response_model=GemListResponse,
    summary="Listar Gems",
    description="Lista todas as Gems do usuário.",
)
async def list_gems(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GemListResponse:
    """Lista todas as Gems do usuário."""
    query = (
        select(Gem)
        .where(Gem.user_id == current_user.id)
        .order_by(Gem.created_at.desc())
        .options(selectinload(Gem.documents))
    )
    result = await db.execute(query)
    gems = result.scalars().unique().all()
    
    gem_responses = []
    for gem in gems:
        gem_responses.append(
            GemResponse(
                id=gem.id,
                name=gem.name,
                description=gem.description,
                instructions=gem.instructions,
                documents=[
                    GemDocumentResponse(
                        id=doc.id,
                        filename=doc.filename,
                        file_size=doc.file_size,
                        created_at=doc.created_at.isoformat(),
                    )
                    for doc in gem.documents
                ],
                created_at=gem.created_at.isoformat(),
                updated_at=gem.updated_at.isoformat(),
            )
        )
    
    return GemListResponse(gems=gem_responses, total=len(gem_responses))


@router.get(
    "/{gem_id}",
    response_model=GemResponse,
    summary="Obter Gem",
    description="Obtém uma Gem específica.",
)
async def get_gem(
    gem_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GemResponse:
    """Obtém uma Gem específica."""
    query = (
        select(Gem)
        .where(Gem.id == gem_id, Gem.user_id == current_user.id)
        .options(selectinload(Gem.documents))
    )
    result = await db.execute(query)
    gem = result.scalar_one_or_none()
    
    if not gem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gem não encontrada"
        )
    
    return GemResponse(
        id=gem.id,
        name=gem.name,
        description=gem.description,
        instructions=gem.instructions,
        documents=[
            {
                "id": doc.id,
                "filename": doc.filename,
                "file_size": doc.file_size,
                "created_at": doc.created_at.isoformat(),
            }
            for doc in gem.documents
        ],
        created_at=gem.created_at.isoformat(),
        updated_at=gem.updated_at.isoformat(),
    )


@router.put(
    "/{gem_id}",
    response_model=GemResponse,
    summary="Atualizar Gem",
    description="Atualiza uma Gem existente.",
)
async def update_gem(
    gem_id: UUID,
    gem_data: GemUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GemResponse:
    """Atualiza uma Gem."""
    query = select(Gem).where(Gem.id == gem_id, Gem.user_id == current_user.id)
    result = await db.execute(query)
    gem = result.scalar_one_or_none()
    
    if not gem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gem não encontrada"
        )
    
    if gem_data.name is not None:
        gem.name = gem_data.name
    if gem_data.description is not None:
        gem.description = gem_data.description
    if gem_data.instructions is not None:
        gem.instructions = gem_data.instructions
    
    await db.commit()
    await db.refresh(gem)
    
    # Recarregar com documentos
    await db.refresh(gem, ["documents"])
    
    return GemResponse(
        id=gem.id,
        name=gem.name,
        description=gem.description,
        instructions=gem.instructions,
        documents=[
            {
                "id": doc.id,
                "filename": doc.filename,
                "file_size": doc.file_size,
                "created_at": doc.created_at.isoformat(),
            }
            for doc in gem.documents
        ],
        created_at=gem.created_at.isoformat(),
        updated_at=gem.updated_at.isoformat(),
    )


@router.delete(
    "/{gem_id}",
    status_code=status.HTTP_200_OK,
    summary="Deletar Gem",
    description="Deleta uma Gem e todos os seus documentos.",
)
async def delete_gem(
    gem_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Deleta uma Gem."""
    query = select(Gem).where(Gem.id == gem_id, Gem.user_id == current_user.id)
    result = await db.execute(query)
    gem = result.scalar_one_or_none()
    
    if not gem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gem não encontrada"
        )
    
    # Deletar arquivos físicos
    for doc in gem.documents:
        file_path = Path(doc.file_path)
        if file_path.exists():
            file_path.unlink()
    
    await db.delete(gem)
    await db.commit()
    
    return {"message": "Gem deletada com sucesso"}


@router.post(
    "/{gem_id}/documents",
    response_model=GemResponse,
    summary="Adicionar documento à Gem",
    description="Adiciona um PDF à Gem e processa com RAG rápido.",
)
async def add_document_to_gem(
    gem_id: UUID,
    file: UploadFile = File(...),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> GemResponse:
    """Adiciona um PDF à Gem e processa com RAG."""
    # Validar Gem
    query = select(Gem).where(Gem.id == gem_id, Gem.user_id == current_user.id)
    result = await db.execute(query)
    gem = result.scalar_one_or_none()
    
    if not gem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gem não encontrada"
        )
    
    # Validar arquivo
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Apenas arquivos PDF são permitidos"
        )
    
    if file.size and file.size > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo muito grande. Máximo: 10MB"
        )
    
    # Criar diretório se não existir
    gem_dir = GEMS_STORAGE / str(gem_id)
    gem_dir.mkdir(parents=True, exist_ok=True)
    
    # Salvar arquivo
    file_path = gem_dir / file.filename
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Criar registro no banco
    gem_doc = GemDocument(
        gem_id=gem.id,
        filename=file.filename,
        file_path=str(file_path),
        file_size=len(content),
    )
    db.add(gem_doc)
    await db.commit()
    await db.refresh(gem_doc)
    
    # Processar PDF com RAG (assíncrono, não bloqueia)
    try:
        await GemRAGService.process_pdf_for_gem(
            gem_id=gem.id,
            document_id=gem_doc.id,
            file_path=str(file_path),
            db=db,
        )
    except Exception as e:
        print(f"[GEM-UPLOAD] ⚠️ Erro ao processar PDF: {e}")
        # Não falhar o upload, apenas logar o erro
    
    # Recarregar Gem com documentos
    await db.refresh(gem, ["documents"])
    
    return GemResponse(
        id=gem.id,
        name=gem.name,
        description=gem.description,
        instructions=gem.instructions,
        documents=[
            {
                "id": doc.id,
                "filename": doc.filename,
                "file_size": doc.file_size,
                "created_at": doc.created_at.isoformat(),
            }
            for doc in gem.documents
        ],
        created_at=gem.created_at.isoformat(),
        updated_at=gem.updated_at.isoformat(),
    )


@router.delete(
    "/{gem_id}/documents/{document_id}",
    status_code=status.HTTP_200_OK,
    summary="Remover documento da Gem",
    description="Remove um documento da Gem.",
)
async def remove_document_from_gem(
    gem_id: UUID,
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Remove um documento da Gem."""
    # Validar Gem
    query = select(Gem).where(Gem.id == gem_id, Gem.user_id == current_user.id)
    result = await db.execute(query)
    gem = result.scalar_one_or_none()
    
    if not gem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gem não encontrada"
        )
    
    # Validar documento
    query = select(GemDocument).where(
        GemDocument.id == document_id,
        GemDocument.gem_id == gem_id,
    )
    result = await db.execute(query)
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento não encontrado"
        )
    
    # Deletar arquivo físico
    file_path = Path(doc.file_path)
    if file_path.exists():
        file_path.unlink()
    
    await db.delete(doc)
    await db.commit()
    
    return {"message": "Documento removido com sucesso"}


@router.post(
    "/{gem_id}/chat",
    response_model=GemChatResponse,
    summary="Chat com Gem",
    description="Conversa com uma Gem específica usando RAG dos documentos.",
)
async def chat_with_gem(
    gem_id: UUID,
    request: GemChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GemChatResponse:
    """Chat com Gem usando RAG."""
    # Validar Gem
    query = select(Gem).where(Gem.id == gem_id, Gem.user_id == current_user.id)
    result = await db.execute(query)
    gem = result.scalar_one_or_none()
    
    if not gem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gem não encontrada"
        )
    
    # Criar agente e responder
    agent = GemAgent(gem)
    response = await agent.chat(
        message=request.message,
        user_id=current_user.id,
        db=db,
    )
    
    return GemChatResponse(
        response=response["response"],
        gem_id=response["gem_id"],
        gem_name=response["gem_name"],
        sources_used=response["sources_used"],
    )

