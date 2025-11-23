"""Service para RAG rápido de documentos das Gems."""

import asyncio
from pathlib import Path
from uuid import UUID

import google.generativeai as genai
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.models.gem import GemDocument, GemDocumentEmbedding
from app.services.embedding_service import EmbeddingService
from app.utils.pdf_processor import PDFProcessor

# Configurar API do Google
genai.configure(api_key=settings.google_api_key)


class GemRAGService:
    """Service para RAG rápido de documentos das Gems."""

    @staticmethod
    async def process_pdf_for_gem(
        gem_id: UUID,
        document_id: UUID,
        file_path: str,
        db: AsyncSession,
    ) -> None:
        """
        Processa PDF e cria embeddings em chunks para RAG rápido.
        
        Args:
            gem_id: ID da Gem.
            document_id: ID do documento.
            file_path: Caminho do arquivo PDF.
            db: Sessão do banco de dados.
        """
        print(f"[GEM-RAG] Processando PDF para Gem {gem_id}...")
        
        # Extrair texto do PDF (assíncrono)
        loop = asyncio.get_event_loop()
        pdf_text = await loop.run_in_executor(
            None,
            PDFProcessor.extract_text_from_pdf,
            file_path
        )
        
        if not pdf_text or len(pdf_text.strip()) < 100:
            print(f"[GEM-RAG] ⚠️ PDF muito pequeno ou vazio ({len(pdf_text) if pdf_text else 0} caracteres)")
            raise ValueError(f"PDF muito pequeno ou vazio. Mínimo necessário: 100 caracteres")
        
        # Chunking melhorado para GEMs (5000 caracteres com overlap de 500 para melhor contexto)
        # Chunks maiores preservam melhor o contexto médico
        chunks = PDFProcessor.chunk_text(pdf_text, chunk_size=5000, overlap=500)
        
        print(f"[GEM-RAG] ✅ PDF extraído: {len(pdf_text):,} caracteres, {len(chunks)} chunks")
        print(f"[GEM-RAG] 📊 Tamanho médio por chunk: {len(pdf_text) // len(chunks) if chunks else 0:,} caracteres")
        
        # Criar embeddings para cada chunk em batch
        embeddings_to_add = []
        total_chunks = len(chunks)
        
        print(f"[GEM-RAG] 🔄 Gerando embeddings para {total_chunks} chunks...")
        for idx, chunk in enumerate(chunks):
            try:
                # Gerar embedding
                embedding_vector = EmbeddingService.generate_embedding(chunk)
                
                # Criar embedding record
                gem_embedding = GemDocumentEmbedding(
                    document_id=document_id,
                    embedding=embedding_vector,
                    embedding_model=settings.embedding_model,
                    chunk_text=chunk,
                    chunk_index=idx,
                )
                embeddings_to_add.append(gem_embedding)
                
                # Log de progresso a cada 10 chunks
                if (idx + 1) % 10 == 0 or (idx + 1) == total_chunks:
                    print(f"[GEM-RAG] 📊 Progresso: {idx + 1}/{total_chunks} chunks processados ({(idx + 1) / total_chunks * 100:.1f}%)")
            except Exception as e:
                print(f"[GEM-RAG] ⚠️ Erro ao processar chunk {idx + 1}: {e}")
                # Continuar com os outros chunks
                continue
        
        if not embeddings_to_add:
            raise ValueError("Nenhum embedding foi gerado com sucesso")
        
        # Batch insert
        print(f"[GEM-RAG] 💾 Salvando {len(embeddings_to_add)} embeddings no banco...")
        db.add_all(embeddings_to_add)
        await db.commit()
        
        print(f"[GEM-RAG] ✅ {len(embeddings_to_add)} embeddings criados e salvos com sucesso")

    @staticmethod
    async def search_gem_documents(
        query: str,
        gem_id: UUID,
        db: AsyncSession,
        limit: int = 10,  # Aumentado de 5 para 10 para mais contexto
        similarity_threshold: float = 0.25,  # Reduzido de 0.3 para 0.25 para capturar mais resultados relevantes
    ) -> list[dict]:
        """
        Busca semântica nos documentos da Gem.
        
        Args:
            query: Query de busca.
            gem_id: ID da Gem.
            db: Sessão do banco de dados.
            limit: Número máximo de resultados.
            similarity_threshold: Limiar mínimo de similaridade (0-1).
        
        Returns:
            list[dict]: Lista de chunks relevantes com scores.
        """
        # Gerar embedding da query
        query_embedding = EmbeddingService.generate_query_embedding(query)
        
        # Busca por similaridade de cosseno
        query_text = text(
            """
            SELECT 
                gde.id,
                gde.chunk_text,
                gde.chunk_index,
                gd.filename,
                1 - (gde.embedding <=> :query_embedding) as similarity
            FROM gem_document_embeddings gde
            INNER JOIN gem_documents gd ON gde.document_id = gd.id
            WHERE gd.gem_id = :gem_id
            AND 1 - (gde.embedding <=> :query_embedding) > :threshold
            ORDER BY gde.embedding <=> :query_embedding
            LIMIT :limit
            """
        )
        
        result = await db.execute(
            query_text,
            {
                "query_embedding": str(query_embedding),
                "gem_id": str(gem_id),
                "threshold": similarity_threshold,
                "limit": limit,
            }
        )
        
        rows = result.fetchall()
        
        return [
            {
                "id": str(row[0]),
                "chunk_text": row[1],
                "chunk_index": row[2],
                "filename": row[3],
                "similarity": float(row[4]),
            }
            for row in rows
        ]

