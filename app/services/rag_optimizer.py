"""Serviço de otimização de RAG para máxima precisão e eficiência."""

import hashlib
import time
from functools import lru_cache
from typing import Dict, List, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.services.embedding_service import EmbeddingService


class RAGOptimizer:
    """Otimizador de RAG para melhorar precisão e eficiência."""

    # Cache de embeddings (em memória)
    _embedding_cache: Dict[str, List[float]] = {}
    _cache_ttl: Dict[str, float] = {}
    CACHE_TTL_SECONDS = 3600  # 1 hora

    @staticmethod
    def _get_query_hash(query: str) -> str:
        """Gera hash da query para cache."""
        return hashlib.md5(query.lower().strip().encode()).hexdigest()

    @classmethod
    def get_cached_embedding(cls, query: str) -> Optional[List[float]]:
        """Retorna embedding do cache se disponível."""
        query_hash = cls._get_query_hash(query)
        if query_hash in cls._embedding_cache:
            if time.time() - cls._cache_ttl.get(query_hash, 0) < cls.CACHE_TTL_SECONDS:
                return cls._embedding_cache[query_hash]
            else:
                # Cache expirado
                del cls._embedding_cache[query_hash]
                del cls._cache_ttl[query_hash]
        return None

    @classmethod
    def cache_embedding(cls, query: str, embedding: List[float]) -> None:
        """Armazena embedding no cache."""
        query_hash = cls._get_query_hash(query)
        cls._embedding_cache[query_hash] = embedding
        cls._cache_ttl[query_hash] = time.time()

    @staticmethod
    def expand_query(query: str) -> str:
        """
        Expande a query com sinônimos e termos relacionados médicos.
        Melhora a recuperação de documentos relevantes.
        """
        # Dicionário de sinônimos médicos comuns
        medical_synonyms = {
            "dor": ["dor", "dolor", "algia", "desconforto"],
            "cabeça": ["cabeça", "crânio", "cefaleia", "cefaléia"],
            "enjoo": ["enjoo", "náusea", "nausea", "vômito", "vomito"],
            "febre": ["febre", "hipertermia", "pirexia"],
            "tosse": ["tosse", "tossir"],
            "prescrição": ["prescrição", "receita", "prescrever", "medicação"],
            "tratamento": ["tratamento", "terapia", "terapêutica", "conduta"],
            "diagnóstico": ["diagnóstico", "diagnostico", "diagnose"],
        }

        # Expandir query com sinônimos
        expanded_terms = []
        query_lower = query.lower()
        
        for word in query.split():
            word_lower = word.lower()
            if word_lower in medical_synonyms:
                expanded_terms.extend(medical_synonyms[word_lower])
            else:
                expanded_terms.append(word)
        
        # Retornar query original + termos expandidos (sem duplicatas)
        expanded_query = " ".join(list(dict.fromkeys(expanded_terms)))
        return expanded_query if expanded_query != query else query

    @staticmethod
    def calculate_relevance_score(
        similarity: float,
        is_favorite: bool = False,
        recency_days: int = 365,
        has_tags: bool = False,
    ) -> float:
        """
        Calcula score de relevância combinado.
        
        Fatores:
        - Similaridade semântica (peso: 0.6)
        - É favorito (peso: 0.15)
        - Recência (peso: 0.15)
        - Tem tags (peso: 0.1)
        """
        base_score = similarity * 0.6
        
        # Bonus por favorito
        favorite_bonus = 0.15 if is_favorite else 0.0
        
        # Bonus por recência (mais recente = maior bonus)
        recency_bonus = max(0, 0.15 * (1 - min(recency_days, 365) / 365))
        
        # Bonus por ter tags (mais organizado)
        tags_bonus = 0.1 if has_tags else 0.0
        
        final_score = base_score + favorite_bonus + recency_bonus + tags_bonus
        return min(1.0, final_score)  # Cap em 1.0

    @staticmethod
    def adaptive_threshold(
        results: List[Dict[str, Any]],
        min_threshold: float = 0.2,
        max_threshold: float = 0.7,
    ) -> float:
        """
        Calcula threshold adaptativo baseado na qualidade dos resultados.
        
        Se os resultados têm alta similaridade, aumenta o threshold.
        Se os resultados têm baixa similaridade, diminui o threshold.
        """
        if not results:
            return min_threshold
        
        avg_similarity = sum(r.get("similarity", 0) for r in results) / len(results)
        
        # Ajustar threshold baseado na média
        if avg_similarity > 0.6:
            # Resultados muito relevantes - ser mais seletivo
            return min(max_threshold, avg_similarity - 0.1)
        elif avg_similarity < 0.3:
            # Resultados pouco relevantes - ser menos seletivo
            return max(min_threshold, avg_similarity - 0.05)
        else:
            # Resultados médios - usar threshold padrão
            return min_threshold

    @staticmethod
    def rerank_results(
        results: List[Dict[str, Any]],
        query: str,
    ) -> List[Dict[str, Any]]:
        """
        Re-rankeia resultados usando múltiplos fatores.
        
        Ordena por:
        1. Score de relevância combinado
        2. Similaridade semântica
        3. Recência
        """
        for result in results:
            # Calcular recência em dias
            created_at = result.get("created_at")
            if created_at:
                if isinstance(created_at, str):
                    # Tentar parsear ISO format
                    try:
                        if created_at.endswith('Z'):
                            created_at = created_at[:-1]
                        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    except:
                        created_at = datetime.now()
                if hasattr(created_at, 'replace'):
                    if created_at.tzinfo:
                        created_at = created_at.replace(tzinfo=None)
                recency_days = (datetime.now() - created_at).days
            else:
                recency_days = 365
            
            # Calcular score de relevância
            relevance_score = RAGOptimizer.calculate_relevance_score(
                similarity=result.get("similarity", 0),
                is_favorite=result.get("is_favorite", False),
                recency_days=recency_days,
                has_tags=bool(result.get("tags")),
            )
            
            result["relevance_score"] = relevance_score
        
        # Ordenar por relevance_score (decrescente)
        results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        
        return results

    @staticmethod
    async def optimized_semantic_search(
        query: str,
        user_id: UUID,
        db: AsyncSession,
        limit: int = 5,
        similarity_threshold: float = 0.2,
        use_cache: bool = True,
        expand_query: bool = True,
        rerank: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Busca semântica otimizada com cache, expansão de query e re-ranking.
        
        Args:
            query: Query de busca
            user_id: ID do usuário
            db: Sessão do banco
            limit: Limite de resultados
            similarity_threshold: Threshold inicial
            use_cache: Usar cache de embeddings
            expand_query: Expandir query com sinônimos
            rerank: Re-ranquear resultados
        
        Returns:
            Lista de resultados otimizados
        """
        # 1. Expandir query se habilitado
        search_query = RAGOptimizer.expand_query(query) if expand_query else query
        
        # 2. Tentar obter embedding do cache
        query_embedding = None
        if use_cache:
            query_embedding = RAGOptimizer.get_cached_embedding(search_query)
        
        # 3. Gerar embedding se não estiver no cache
        if query_embedding is None:
            query_embedding = EmbeddingService.generate_query_embedding(search_query)
            if use_cache:
                RAGOptimizer.cache_embedding(search_query, query_embedding)
        
        # 4. Buscar no banco com threshold inicial
        sql_query = text(
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
            sql_query,
            {
                "query_embedding": str(query_embedding),
                "user_id": str(user_id),
                "threshold": similarity_threshold,
                "limit": limit * 2,  # Buscar mais para re-ranking
            },
        )
        
        rows = result.fetchall()
        
        # 5. Formatar resultados
        results = []
        for row in rows:
            results.append(
                {
                    "id": str(row[0]),
                    "title": row[1],
                    "content": row[2],
                    "tags": row[3] or [],
                    "is_favorite": row[4],
                    "created_at": row[5],
                    "updated_at": row[6],
                    "similarity": round(float(row[7]), 4),
                }
            )
        
        # 6. Aplicar threshold adaptativo
        if results:
            adaptive_threshold = RAGOptimizer.adaptive_threshold(results)
            results = [r for r in results if r["similarity"] >= adaptive_threshold]
        
        # 7. Re-ranquear se habilitado
        if rerank:
            results = RAGOptimizer.rerank_results(results, query)
        
        # 8. Retornar top N resultados
        return results[:limit]

    @staticmethod
    def validate_response_quality(
        response: str,
        query: str,
        context_used: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Valida a qualidade da resposta gerada.
        
        Retorna métricas de qualidade:
        - has_relevant_content: Se a resposta é relevante
        - uses_context: Se usa o contexto fornecido
        - completeness: Completude da resposta (0-1)
        """
        response_lower = response.lower()
        query_lower = query.lower()
        
        # Verificar se a resposta menciona termos da query
        query_terms = set(query_lower.split())
        response_terms = set(response_lower.split())
        term_overlap = len(query_terms & response_terms) / max(len(query_terms), 1)
        
        # Verificar se usa contexto
        uses_context = len(context_used) > 0 and any(
            term in response_lower for term in ["anotação", "documento", "fonte", "protocolo"]
        )
        
        # Completude (respostas muito curtas são incompletas)
        min_length = 50
        completeness = min(1.0, len(response) / min_length) if len(response) >= min_length else 0.0
        
        # Score geral
        quality_score = (term_overlap * 0.4 + (1.0 if uses_context else 0.0) * 0.4 + completeness * 0.2)
        
        return {
            "quality_score": round(quality_score, 2),
            "term_overlap": round(term_overlap, 2),
            "uses_context": uses_context,
            "completeness": round(completeness, 2),
            "is_high_quality": quality_score >= 0.6,
        }

