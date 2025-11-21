"""Service para RAG (Retrieval Augmented Generation)."""

from uuid import UUID

import asyncio
import google.generativeai as genai
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.models.note import Note
from app.models.note_embedding import NoteEmbedding
from app.services.embedding_service import EmbeddingService

# Configurar API do Google
genai.configure(api_key=settings.google_api_key)


class RAGService:
    """Service para busca semântica e geração com RAG."""

    @staticmethod
    async def semantic_search(
        query: str,
        user_id: UUID,
        db: AsyncSession,
        limit: int = 5,
        similarity_threshold: float = 0.3,
    ) -> list[dict]:
        """
        Busca semântica usando embeddings.

        Args:
            query: Query de busca.
            user_id: ID do usuário (para filtrar resultados).
            db: Sessão do banco de dados.
            limit: Número máximo de resultados.
            similarity_threshold: Limiar mínimo de similaridade (0-1).

        Returns:
            list[dict]: Lista de anotações relevantes com scores.
        """
        # Gerar embedding da query
        query_embedding = EmbeddingService.generate_query_embedding(query)

        # Busca por similaridade de cosseno
        # pgvector usa operador <=> para distância de cosseno
        # Convertemos para similaridade: 1 - distance
        query_text = text(
            """
            SELECT 
                n.id,
                n.title,
                n.content,
                n.tags,
                n.is_favorite,
                n.created_at,
                n.updated_at,
                1 - (ne.embedding <=> :query_embedding) as similarity
            FROM notes n
            INNER JOIN note_embeddings ne ON n.id = ne.note_id
            WHERE n.user_id = :user_id
            AND 1 - (ne.embedding <=> :query_embedding) > :threshold
            ORDER BY ne.embedding <=> :query_embedding
            LIMIT :limit
            """
        )

        result = await db.execute(
            query_text,
            {
                "query_embedding": str(query_embedding),
                "user_id": str(user_id),
                "threshold": similarity_threshold,
                "limit": limit,
            },
        )

        rows = result.fetchall()

        # Formatar resultados
        results = []
        for row in rows:
            results.append(
                {
                    "id": str(row[0]),
                    "title": row[1],
                    "content": row[2],
                    "tags": row[3],
                    "is_favorite": row[4],
                    "created_at": row[5].isoformat(),
                    "updated_at": row[6].isoformat(),
                    "similarity": round(float(row[7]), 4),
                }
            )

        return results

    @staticmethod
    async def search_documents(
        query: str,
        user_id: UUID,
        db: AsyncSession,
        limit: int = 3,
        similarity_threshold: float = 0.2,
    ) -> list[dict]:
        """
        Busca semântica em documentos PDF do usuário.
        
        Args:
            query: Consulta de busca.
            user_id: ID do usuário.
            db: Sessão do banco.
            limit: Número de resultados.
            similarity_threshold: Limiar de similaridade.
            
        Returns:
            Lista de documentos relevantes.
        """
        from app.models.document import Document
        from app.models.document_embedding import DocumentEmbedding
        
        # Gerar embedding da query
        query_embedding = EmbeddingService.generate_query_embedding(query)
        
        # SQL para buscar documentos similares
        sql = text("""
            SELECT 
                d.id,
                d.filename,
                d.description,
                de.content_preview,
                d.created_at,
                1 - (de.embedding <=> CAST(:query_embedding AS vector)) as similarity
            FROM documents d
            JOIN document_embeddings de ON d.id = de.document_id
            WHERE d.user_id = :user_id
            AND 1 - (de.embedding <=> CAST(:query_embedding AS vector)) > :similarity_threshold
            ORDER BY de.embedding <=> CAST(:query_embedding AS vector)
            LIMIT :limit
        """)
        
        result = await db.execute(
            sql,
            {
                "query_embedding": str(query_embedding),
                "user_id": user_id,
                "similarity_threshold": similarity_threshold,
                "limit": limit,
            },
        )
        
        results = []
        for row in result:
            results.append(
                {
                    "id": str(row[0]),
                    "title": row[1],  # filename
                    "content": row[3],  # content_preview
                    "type": "document",  # Identificar como documento
                    "created_at": row[4].isoformat(),
                    "similarity": round(float(row[5]), 4),
                }
            )
        
        return results

    @staticmethod
    async def ask_with_context(
        question: str,
        user_id: UUID,
        db: AsyncSession,
        context_limit: int = 3,
    ) -> dict:
        """
        Responde uma pergunta usando RAG (busca + geração).
        BUSCA EM ANOTAÇÕES E DOCUMENTOS!

        Args:
            question: Pergunta do usuário.
            user_id: ID do usuário.
            db: Sessão do banco de dados.
            context_limit: Número de itens para usar como contexto.

        Returns:
            dict: Resposta gerada e contexto usado.
        """
        # Buscar contexto relevante em ANOTAÇÕES
        context_notes = await RAGService.semantic_search(
            query=question,
            user_id=user_id,
            db=db,
            limit=context_limit,
            similarity_threshold=0.2,
        )
        
        # Buscar contexto relevante em DOCUMENTOS
        context_documents = await RAGService.search_documents(
            query=question,
            user_id=user_id,
            db=db,
            limit=context_limit,
            similarity_threshold=0.2,
        )
        
        # Combinar resultados
        all_context = context_notes + context_documents
        
        # Ordenar por similaridade e pegar os top N
        all_context.sort(key=lambda x: x["similarity"], reverse=True)
        all_context = all_context[:context_limit * 2]  # Pegar mais itens para ter variedade
        
        print(f"📊 Contexto encontrado: {len(context_notes)} notas + {len(context_documents)} documentos")

        # Se não encontrou contexto relevante
        if not all_context:
            return {
                "answer": "Desculpe, não encontrei informações relevantes nas suas anotações ou documentos para responder essa pergunta. Talvez você possa adicionar mais conteúdo?",
                "context_used": [],
                "has_context": False,
            }

        # Construir prompt com contexto (notas + documentos)
        context_parts = []
        
        for item in all_context:
            if item.get("type") == "document":
                # É um documento PDF
                context_parts.append(
                    f"**📄 {item['title']}** (Documento PDF)\n{item['content']}"
                )
            else:
                # É uma anotação
                tags_str = ", ".join(item.get("tags", [])) if item.get("tags") else ""
                context_parts.append(
                    f"**📝 {item['title']}**\n{item['content']}\nTags: {tags_str}"
                )
        
        context_text = "\n\n---\n\n".join(context_parts)

        prompt = f"""Você é uma assistente médica especializada. Use APENAS as informações das anotações e documentos abaixo para responder a pergunta.

**SUAS ANOTAÇÕES E DOCUMENTOS RELEVANTES:**

{context_text}

---

**PERGUNTA DO USUÁRIO:**
{question}

**INSTRUÇÕES:**
- Responda em português (pt-BR)
- Use APENAS informações presentes nas anotações e documentos acima
- Seja clara, precisa e técnica
- Se a informação não estiver disponível, diga explicitamente
- Cite as fontes relevantes (anotações 📝 ou documentos 📄) na sua resposta
- Forneça uma resposta estruturada e fácil de entender

**RESPOSTA:**"""

        # Gerar resposta com Gemini (com retry para rate limiting)
        import time
        from google.api_core import exceptions as google_exceptions
        
        # Configurar modelo com parâmetros de geração
        generation_config = {
            "max_output_tokens": settings.max_output_tokens,
            "top_k": settings.top_k,
            "temperature": 0.7,
        }
        model = genai.GenerativeModel(
            settings.gemini_model,
            generation_config=generation_config,
        )
        
        # Tentar com retry exponencial
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = model.generate_content(prompt)
                break  # Sucesso, sair do loop
            except google_exceptions.ResourceExhausted as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 2  # 2s, 4s, 8s
                    print(f"⚠️ Rate limit atingido. Aguardando {wait_time}s antes de tentar novamente...")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"❌ Rate limit excedido após {max_retries} tentativas")
                    return {
                        "answer": "Desculpe, estou temporariamente sobrecarregada. Por favor, aguarde alguns segundos e tente novamente. 😔",
                        "context_used": [],
                        "has_context": False,
                    }
            except Exception as e:
                print(f"❌ Erro ao gerar resposta: {e}")
                return {
                    "answer": f"Desculpe, ocorreu um erro ao processar sua pergunta: {str(e)}",
                    "context_used": [],
                    "has_context": False,
                }

        return {
            "answer": response.text,
            "context_used": [
                {
                    "id": item["id"],
                    "title": item["title"],
                    "similarity": item["similarity"],
                    "type": item.get("type", "note"),  # note ou document
                }
                for item in all_context
            ],
            "has_context": True,
        }

    @staticmethod
    async def reindex_all_notes(user_id: UUID, db: AsyncSession) -> dict:
        """
        Reindexa todas as anotações de um usuário.

        Args:
            user_id: ID do usuário.
            db: Sessão do banco de dados.

        Returns:
            dict: Estatísticas da reindexação.
        """
        # Buscar todas as notas do usuário
        result = await db.execute(select(Note).where(Note.user_id == user_id))
        notes = result.scalars().all()

        indexed = 0
        errors = 0

        for note in notes:
            try:
                await EmbeddingService.create_or_update_embedding(note, db)
                indexed += 1
            except Exception as e:
                errors += 1
                print(f"Erro ao indexar nota {note.id}: {e}")

        return {
            "total_notes": len(notes),
            "indexed": indexed,
            "errors": errors,
        }

