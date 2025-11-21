"""Indexação de documentos oficiais para RAG."""

import asyncio
from pathlib import Path
from typing import Dict, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.official_document import OfficialDocument
from app.models.official_document_embedding import OfficialDocumentEmbedding
from app.services.embedding_service import EmbeddingService
from app.utils.pdf_processor import PDFProcessor
from app.config.settings import settings


class OfficialDocumentIndexer:
    """Indexa documentos oficiais para busca semântica."""

    @staticmethod
    async def index_source(
        source_name: str,
        source_dir: Path,
        db: AsyncSession,
        priority: int,
        specialty: str,
    ) -> Dict[str, int]:
        """
        Indexa todos os PDFs de uma fonte oficial.

        Args:
            source_name: Nome da fonte (pcdt, sbc, etc.)
            source_dir: Diretório com os PDFs
            db: Sessão do banco de dados
            priority: Prioridade da fonte (1 = mais alta)
            specialty: Especialidade médica

        Returns:
            Dict[str, int]: Estatísticas da indexação
        """
        pdf_files = list(source_dir.glob("*.pdf"))

        total = len(pdf_files)
        indexed = 0
        skipped = 0
        errors = []

        print(f"\n📊 Indexando {source_name.upper()}: {total} PDFs encontrados")

        for pdf_file in pdf_files:
            try:
                # Verificar se já foi indexado
                existing = await db.execute(
                    select(OfficialDocument).where(
                        OfficialDocument.source == source_name,
                        OfficialDocument.file_path == str(pdf_file),
                    )
                )
                if existing.scalar_one_or_none():
                    print(f"   ⏭️ Já indexado: {pdf_file.name}")
                    skipped += 1
                    continue

                # Extrair texto
                print(f"   📄 Processando: {pdf_file.name}")
                text = PDFProcessor.extract_text_from_pdf(pdf_file)

                if not text or len(text.strip()) < 100:
                    print(f"   ⚠️ Texto muito curto ou vazio: {pdf_file.name}")
                    errors.append({"file": pdf_file.name, "error": "Texto vazio"})
                    continue

                # Limitar texto para embedding (30.000 caracteres)
                text_preview = text[:30000]

                # Criar documento oficial
                doc = OfficialDocument(
                    source=source_name,
                    title=pdf_file.stem,
                    url=f"file://{pdf_file}",
                    file_path=str(pdf_file),
                    priority=priority,
                    specialty=specialty,
                )

                db.add(doc)
                await db.commit()
                await db.refresh(doc)

                # Gerar embedding
                try:
                    embedding_vector = EmbeddingService.generate_embedding(text_preview)

                    doc_embedding = OfficialDocumentEmbedding(
                        document_id=doc.id,
                        content_preview=text[:500],  # Preview menor
                        embedding=embedding_vector,
                    )

                    db.add(doc_embedding)
                    await db.commit()

                    indexed += 1
                    print(f"   ✅ Indexado: {pdf_file.name}")

                except Exception as e:
                    print(f"   ❌ Erro ao gerar embedding para {pdf_file.name}: {e}")
                    errors.append({"file": pdf_file.name, "error": str(e)})
                    # Documento foi criado mas sem embedding
                    continue

            except Exception as e:
                errors.append({"file": pdf_file.name, "error": str(e)})
                print(f"   ❌ Erro ao indexar {pdf_file.name}: {e}")

        print(f"\n📊 Resultado da indexação de {source_name.upper()}:")
        print(f"   Total: {total}")
        print(f"   Indexados: {indexed}")
        print(f"   Já existiam: {skipped}")
        print(f"   Erros: {len(errors)}")

        return {
            "total": total,
            "indexed": indexed,
            "skipped": skipped,
            "errors": len(errors),
            "error_details": errors,
        }

    @staticmethod
    async def index_all_sources(db: AsyncSession) -> Dict[str, Dict]:
        """
        Indexa todas as fontes oficiais disponíveis.

        Args:
            db: Sessão do banco de dados

        Returns:
            Dict[str, Dict]: Estatísticas por fonte
        """
        from app.official_sources.downloader import OfficialSourceDownloader

        downloader = OfficialSourceDownloader()
        results = {}

        for source_name, source_config in downloader.SOURCES.items():
            source_dir = downloader.official_docs_path / source_name

            if not source_dir.exists() or not list(source_dir.glob("*.pdf")):
                print(f"\n⚠️ Nenhum PDF encontrado em {source_dir}")
                results[source_name] = {
                    "total": 0,
                    "indexed": 0,
                    "skipped": 0,
                    "errors": 0,
                    "error_details": [],
                }
                continue

            stats = await OfficialDocumentIndexer.index_source(
                source_name=source_name,
                source_dir=source_dir,
                db=db,
                priority=source_config["priority"],
                specialty=source_config["specialty"],
            )

            results[source_name] = stats

        return results

    @staticmethod
    async def reindex_document(
        document_id: UUID, db: AsyncSession
    ) -> bool:
        """
        Reindexa um documento específico.

        Args:
            document_id: ID do documento
            db: Sessão do banco de dados

        Returns:
            bool: True se reindexado com sucesso
        """
        # Buscar documento
        result = await db.execute(
            select(OfficialDocument).where(OfficialDocument.id == document_id)
        )
        doc = result.scalar_one_or_none()

        if not doc:
            print(f"❌ Documento {document_id} não encontrado")
            return False

        try:
            # Extrair texto novamente
            pdf_path = Path(doc.file_path)
            if not pdf_path.exists():
                print(f"❌ Arquivo não encontrado: {pdf_path}")
                return False

            text = PDFProcessor.extract_text_from_pdf(pdf_path)
            text_preview = text[:30000]

            # Gerar novo embedding
            embedding_vector = EmbeddingService.generate_embedding(text_preview)

            # Atualizar ou criar embedding
            existing_embedding = await db.execute(
                select(OfficialDocumentEmbedding).where(
                    OfficialDocumentEmbedding.document_id == document_id
                )
            )
            embedding = existing_embedding.scalar_one_or_none()

            if embedding:
                embedding.embedding = embedding_vector
                embedding.content_preview = text[:500]
            else:
                embedding = OfficialDocumentEmbedding(
                    document_id=document_id,
                    content_preview=text[:500],
                    embedding=embedding_vector,
                )
                db.add(embedding)

            await db.commit()
            print(f"✅ Documento {document_id} reindexado com sucesso")
            return True

        except Exception as e:
            print(f"❌ Erro ao reindexar documento {document_id}: {e}")
            return False

