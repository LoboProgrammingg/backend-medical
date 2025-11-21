"""Endpoints para gerenciamento de fontes oficiais."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.config.database import get_db
from app.models.user import User
from app.models.official_document import OfficialDocument
from app.core.dependencies import get_current_user
from app.official_sources.downloader import OfficialSourceDownloader
from app.official_sources.indexer import OfficialDocumentIndexer
from app.config.settings import settings

router = APIRouter(prefix="/official-sources", tags=["Official Sources"])


@router.post(
    "/download",
    status_code=status.HTTP_200_OK,
    summary="Baixar fontes oficiais",
    description="Baixa documentos de todas as fontes oficiais (PCDT, SBC, SBOC, AMIB, SBP).",
)
async def download_official_sources(
    limit_per_source: int = 10,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """Baixa todas as fontes oficiais."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado"
        )

    try:
        downloader = OfficialSourceDownloader(storage_path=settings.storage_path)
        results = await downloader.download_all_sources(limit_per_source=limit_per_source)

        return {
            "status": "success",
            "message": "Download concluído",
            "downloaded": results,
            "total": sum(results.values()),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao baixar fontes oficiais: {str(e)}",
        )


@router.post(
    "/download/{source_name}",
    status_code=status.HTTP_200_OK,
    summary="Baixar fonte específica",
    description="Baixa documentos de uma fonte oficial específica.",
)
async def download_source(
    source_name: str,
    limit: int = 10,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """Baixa uma fonte específica."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado"
        )

    try:
        downloader = OfficialSourceDownloader(storage_path=settings.storage_path)
        
        # Verificar se a fonte existe
        if source_name not in downloader.SOURCES:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fonte '{source_name}' não encontrada. Fontes disponíveis: {', '.join(downloader.list_sources())}",
            )

        count = await downloader.update_source(source_name, limit=limit)

        return {
            "status": "success",
            "message": f"Download de {source_name} concluído",
            "source": source_name,
            "downloaded": count,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao baixar {source_name}: {str(e)}",
        )


@router.post(
    "/index",
    status_code=status.HTTP_200_OK,
    summary="Indexar fontes oficiais",
    description="Indexa todos os documentos oficiais baixados para busca semântica.",
)
async def index_official_sources(
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """Indexa todos os documentos oficiais baixados."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado"
        )

    try:
        indexer = OfficialDocumentIndexer()
        results = await indexer.index_all_sources(db)

        total_indexed = sum(r["indexed"] for r in results.values())
        total_errors = sum(r["errors"] for r in results.values())

        return {
            "status": "success",
            "message": "Indexação concluída",
            "indexed": results,
            "total_indexed": total_indexed,
            "total_errors": total_errors,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao indexar fontes oficiais: {str(e)}",
        )


@router.get(
    "/status",
    status_code=status.HTTP_200_OK,
    summary="Status das fontes oficiais",
    description="Retorna status e estatísticas das fontes oficiais.",
)
async def get_sources_status(
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """Retorna status das fontes oficiais."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado"
        )

    try:
        downloader = OfficialSourceDownloader(storage_path=settings.storage_path)
        sources_info = {}

        for source_name in downloader.list_sources():
            # Contar documentos no banco
            result = await db.execute(
                select(func.count(OfficialDocument.id)).where(
                    OfficialDocument.source == source_name
                )
            )
            count = result.scalar_one()

            # Pegar último documento atualizado
            last_doc_result = await db.execute(
                select(OfficialDocument.last_updated)
                .where(OfficialDocument.source == source_name)
                .order_by(OfficialDocument.last_updated.desc())
                .limit(1)
            )
            last_updated = last_doc_result.scalar_one_or_none()

            source_config = downloader.get_source_info(source_name)

            sources_info[source_name] = {
                "description": source_config["description"],
                "specialty": source_config["specialty"],
                "priority": source_config["priority"],
                "documents_indexed": count,
                "last_updated": last_updated.isoformat() if last_updated else None,
            }

        # Total geral
        total_result = await db.execute(select(func.count(OfficialDocument.id)))
        total_documents = total_result.scalar_one()

        return {
            "status": "success",
            "sources": sources_info,
            "total_documents": total_documents,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar status: {str(e)}",
        )


@router.get(
    "/sources",
    status_code=status.HTTP_200_OK,
    summary="Listar fontes disponíveis",
    description="Lista todas as fontes oficiais disponíveis para download.",
)
async def list_sources(
    current_user: Annotated[User, Depends(get_current_user)] = None,
):
    """Lista todas as fontes oficiais disponíveis."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado"
        )

    downloader = OfficialSourceDownloader(storage_path=settings.storage_path)
    sources = []

    for source_name in downloader.list_sources():
        source_config = downloader.get_source_info(source_name)
        sources.append(
            {
                "id": source_name,
                "name": source_name.upper(),
                "description": source_config["description"],
                "specialty": source_config["specialty"],
                "priority": source_config["priority"],
                "url": source_config["base_url"],
            }
        )

    return {"status": "success", "sources": sources}

