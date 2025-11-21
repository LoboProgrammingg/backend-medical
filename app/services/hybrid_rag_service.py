"""Serviço de RAG Híbrido: combina fontes do usuário e oficiais."""

from typing import List, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

import google.generativeai as genai

from app.services.rag_service import RAGService
from app.services.embedding_service import EmbeddingService
from app.services.rag_optimizer import RAGOptimizer
from app.config.settings import settings


class HybridRAGService:
    """RAG que combina anotações do usuário + documentos oficiais."""

    @staticmethod
    async def hybrid_search(
        query: str,
        user_id: UUID,
        db: AsyncSession,
        user_limit: int = 3,
        official_limit: int = 5,
        similarity_threshold: float = 0.2,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Busca híbrida: anotações do usuário + documentos oficiais.

        Priorização:
        1. Anotações do usuário (mais relevante para o contexto pessoal)
        2. Documentos do usuário (PDFs enviados)
        3. Documentos oficiais (PCDT, Sociedades Médicas)

        Args:
            query: Pergunta do usuário
            user_id: ID do usuário
            db: Sessão do banco de dados
            user_limit: Limite de resultados do usuário
            official_limit: Limite de resultados oficiais
            similarity_threshold: Threshold de similaridade

        Returns:
            Dict com user_notes, user_documents, official_documents
        """

        # 1. Buscar nas anotações do usuário (OTIMIZADO)
        user_notes = await RAGOptimizer.optimized_semantic_search(
            query=query,
            user_id=user_id,
            db=db,
            limit=user_limit,
            similarity_threshold=similarity_threshold,
            use_cache=True,
            expand_query=True,
            rerank=True,
        )

        # 2. Buscar nos documentos do usuário (PDFs)
        user_docs = await RAGService.search_documents(
            query=query,
            user_id=user_id,
            db=db,
            limit=user_limit,
            similarity_threshold=similarity_threshold,
        )

        # 3. Buscar nos documentos oficiais
        official_docs = await HybridRAGService._search_official_documents(
            query=query,
            db=db,
            limit=official_limit,
            similarity_threshold=similarity_threshold,
        )

        return {
            "user_notes": user_notes,
            "user_documents": user_docs,
            "official_documents": official_docs,
        }

    @staticmethod
    async def _search_official_documents(
        query: str,
        db: AsyncSession,
        limit: int = 5,
        similarity_threshold: float = 0.2,
    ) -> List[Dict[str, Any]]:
        """
        Busca em documentos oficiais (PCDT, SBC, etc.).

        Args:
            query: Pergunta do usuário
            db: Sessão do banco de dados
            limit: Limite de resultados
            similarity_threshold: Threshold de similaridade

        Returns:
            Lista de documentos oficiais relevantes
        """
        query_embedding = EmbeddingService.generate_query_embedding(query)

        sql_query = text(
            """
            SELECT
                od.id,
                od.source,
                od.title,
                od.specialty,
                od.priority,
                ode.content_preview,
                1 - (ode.embedding <=> CAST(:query_embedding AS vector)) AS similarity
            FROM
                official_documents od
            JOIN
                official_document_embeddings ode ON od.id = ode.document_id
            ORDER BY
                od.priority ASC,  -- Prioridade 1 = mais alta
                similarity DESC
            LIMIT :limit;
            """
        )

        result = await db.execute(
            sql_query,
            {
                "query_embedding": str(query_embedding),
                "limit": limit,
            },
        )
        rows = result.fetchall()

        results = []
        for row in rows:
            if row[6] >= similarity_threshold:  # row[6] = similarity
                results.append(
                    {
                        "type": "official",
                        "source": row[1],  # pcdt, sbc, etc.
                        "id": str(row[0]),
                        "title": row[2],
                        "specialty": row[3],
                        "priority": row[4],
                        "content": row[5],
                        "similarity": round(float(row[6]), 4),
                    }
                )

        return results

    @staticmethod
    async def ask_with_hybrid_rag(
        question: str,
        user_id: UUID,
        db: AsyncSession,
    ) -> dict:
        """
        Responde usando RAG Híbrido com priorização de fontes.

        PRIORIZAÇÃO:
        1. Anotações do usuário (contexto pessoal)
        2. PDFs do usuário
        3. PCDT/Ministério da Saúde (oficial)
        4. Sociedades Médicas (SBC, SBOC, AMIB, SBP)

        Args:
            question: Pergunta do usuário
            user_id: ID do usuário
            db: Sessão do banco de dados

        Returns:
            Dict com answer, context_used, has_context, sources
        """

        # Busca híbrida
        results = await HybridRAGService.hybrid_search(
            query=question,
            user_id=user_id,
            db=db,
            user_limit=3,
            official_limit=5,
        )

        # Construir contexto priorizado
        context_parts = []
        sources = []

        # 1. Prioridade: Anotações do usuário
        for note in results["user_notes"]:
            context_parts.append(
                f"📝 **[SUA ANOTAÇÃO] {note['title']}**\n{note['content']}"
            )
            sources.append(f"📝 Sua anotação: {note['title']}")

        # 2. Prioridade: PDFs do usuário
        for doc in results["user_documents"]:
            context_parts.append(
                f"📄 **[SEU DOCUMENTO] {doc['title']}**\n{doc['content']}"
            )
            sources.append(f"📄 Seu documento: {doc['title']}")

        # 3. Prioridade: Documentos oficiais
        for official in results["official_documents"]:
            emoji = "🏛️" if official["source"] == "pcdt" else "🏥"
            source_label = {
                "pcdt": "PROTOCOLO OFICIAL MS",
                "sbc": "DIRETRIZ SBC (Cardiologia)",
                "sboc": "DIRETRIZ SBOC (Oncologia)",
                "amib": "DIRETRIZ AMIB (UTI)",
                "sbp": "DIRETRIZ SBP (Pediatria)",
            }.get(official["source"], "DOCUMENTO OFICIAL")

            context_parts.append(
                f"{emoji} **[{source_label}] {official['title']}**\n{official['content']}"
            )
            sources.append(f"{emoji} {source_label}: {official['title']}")

        if not context_parts:
            return {
                "answer": "Não encontrei informações relevantes nas suas anotações ou nos protocolos oficiais. Posso buscar na web se quiser! 🌐",
                "context_used": [],  # Lista vazia ao invés de dict
                "has_context": False,
                "sources": [],
            }

        context_text = "\n\n---\n\n".join(context_parts)

        # Prompt com hierarquia de fontes - DIRETO E PRÁTICO
        prompt = f"""Você é uma assistente médica especializada, PRÁTICA e RESOLUTIVA.

**SUA MISSÃO:** Fornecer respostas médicas DIRETAS, PRÁTICAS e COMPLETAS.

**FONTES DISPONÍVEIS (prioridade):**

{context_text}

---

**PERGUNTA DO USUÁRIO:**
{question}

**INSTRUÇÕES CRÍTICAS:**

1. **SEJA DIRETO E PRÁTICO:**
   - Se o usuário pedir uma PRESCRIÇÃO, forneça prescrição COMPLETA com medicamentos, dosagens e posologias
   - Se pedir uma CONDUTA, forneça conduta detalhada e prática
   - Se pedir um TRATAMENTO, forneça tratamento completo e aplicável

2. **NÃO SEJA EXCESSIVAMENTE CAUTELOSA:**
   - Dê respostas práticas baseadas nas fontes disponíveis
   - Não fique apenas explicando "limitações" - FORNEÇA SOLUÇÕES
   - Seja resolutiva e útil

3. **PRIORIZAÇÃO DE FONTES:**
   - PRIORIDADE 1: Anotações do usuário (mais relevante)
   - PRIORIDADE 2: Documentos do usuário (PDFs)
   - PRIORIDADE 3: Protocolos oficiais (PCDT, diretrizes)
   - Se houver conflito, prefira: Anotações > PCDT > Sociedades Médicas

4. **FORMATO DE RESPOSTA:**
   - Use Markdown para estruturação
   - Se for prescrição, use formato: **Medicamento** - Dosagem - Posologia
   - Inclua orientações práticas
   - Cite as fontes usadas (📝 anotações, 📄 documentos, 🏛️ PCDT, 🏥 diretrizes)

5. **EXEMPLOS FEW-SHOT (APRENDA COM ESTES):**

   **Exemplo 1 - Prescrição:**
   Pergunta: "Me fale como que eu receitaria um paciente que está sentindo muito enjoo e dor de cabeça forte"
   Resposta:
   ```
   **PRESCRIÇÃO PARA ENJOO E DOR DE CABEÇA FORTE:**
   
   📋 **Medicamentos:**
   1. **Paracetamol 750mg** - 1 comprimido a cada 8 horas (máximo 3x/dia) - Para dor de cabeça
   2. **Metoclopramida 10mg** - 1 comprimido a cada 8 horas (antes das refeições) - Para enjoo/náusea
      OU
      **Ondansetrona 4mg** - 1 comprimido a cada 12 horas (se metoclopramida não funcionar)
   
   📋 **Orientações:**
   - Repouso relativo
   - Hidratação oral abundante (água, soro caseiro)
   - Alimentação leve e fracionada
   - Evitar alimentos gordurosos e condimentados
   - Retornar se sintomas persistirem por mais de 48h ou piorarem
   
   ⚠️ **Importante:** Avaliar sinais de alarme (rigidez de nuca, vômitos incoercíveis, alteração do nível de consciência)
   ```

   **Exemplo 2 - Tratamento:**
   Pergunta: "Como tratar ICC?"
   Resposta:
   ```
   **TRATAMENTO DE INSUFICIÊNCIA CARDÍACA CONGESTIVA:**
   
   📋 **Farmacológico:**
   - **Enalapril 10mg** - 1 comprimido 2x/dia (IECA - primeira linha)
   - **Carvedilol 25mg** - 1 comprimido 2x/dia (Beta-bloqueador)
   - **Furosemida 40mg** - 1 comprimido pela manhã (Diurético)
   
   📋 **Não-farmacológico:**
   - Restrição de sódio <2g/dia
   - Controle de peso diário
   - Atividade física moderada (após estabilização)
   ```

6. **ESTRATÉGIA DE RESPOSTA:**
   - Use Chain-of-Thought: Pense passo a passo antes de responder
   - Seja específico: Use dosagens exatas, não "algum medicamento"
   - Seja completo: Inclua orientações, contraindicações quando relevante
   - Cite fontes: Sempre mencione de onde veio a informação

**RESPONDA AGORA DE FORMA DIRETA, PRÁTICA E COMPLETA, SEGUINDO OS EXEMPLOS ACIMA:**"""

        # Gerar resposta com Gemini (com retry para rate limiting)
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

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = model.generate_content(prompt)
                break  # Sucesso
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"⚠️ Erro ao gerar resposta (tentativa {attempt + 1}): {e}")
                    import asyncio
                    await asyncio.sleep(2)
                else:
                    print(f"❌ Erro final ao gerar resposta: {e}")
                    # Combinar results em uma lista única
                    all_context = (
                        results["user_notes"] +
                        results["user_documents"] +
                        results["official_documents"]
                    )
                    return {
                        "answer": f"Desculpe, ocorreu um erro ao processar sua pergunta: {str(e)}",
                        "context_used": all_context,
                        "has_context": True,
                        "sources": sources,
                    }

        # Combinar results em uma lista única
        all_context = (
            results["user_notes"] +
            results["user_documents"] +
            results["official_documents"]
        )

        # Validar qualidade da resposta
        quality_metrics = RAGOptimizer.validate_response_quality(
            response=response.text,
            query=question,
            context_used=all_context,
        )
        
        # Se a qualidade for baixa e tiver contexto, tentar melhorar
        if not quality_metrics["is_high_quality"] and all_context:
            print(f"⚠️ Qualidade da resposta baixa ({quality_metrics['quality_score']}). Tentando melhorar...")
            # Pode adicionar lógica de retry aqui se necessário
        
        return {
            "answer": response.text,
            "context_used": all_context,
            "has_context": True,
            "sources": sources,
            "quality_metrics": quality_metrics,  # Adicionar métricas de qualidade
        }

