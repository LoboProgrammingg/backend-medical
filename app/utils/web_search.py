"""Utilitário para busca na web usando Tavily."""

from typing import List, Dict, Any

from tavily import TavilyClient

from app.config.settings import settings


class WebSearchTool:
    """Ferramenta para buscar informações na web."""

    def __init__(self):
        """Inicializa o cliente Tavily."""
        self.client = None
        if settings.tavily_api_key:
            try:
                self.client = TavilyClient(api_key=settings.tavily_api_key)
            except Exception as e:
                print(f"Erro ao inicializar Tavily: {e}")

    def is_available(self) -> bool:
        """Verifica se a busca web está disponível."""
        return self.client is not None

    async def search(
        self, 
        query: str, 
        max_results: int = 3,
        search_depth: str = "advanced",
        include_domains: List[str] | None = None
    ) -> List[Dict[str, Any]]:
        """
        Busca informações na web.

        Args:
            query: Consulta de busca.
            max_results: Número máximo de resultados.
            search_depth: Profundidade da busca ("basic" ou "advanced").
            include_domains: Lista de domínios para incluir (opcional).

        Returns:
            Lista de resultados com título, URL e conteúdo.
        """
        if not self.is_available():
            return []

        try:
            # Adicionar contexto médico à busca
            medical_query = f"{query} medicina saúde"
            
            # Configurar busca com foco em sites médicos confiáveis
            search_kwargs = {
                "query": medical_query,
                "max_results": max_results,
                "search_depth": search_depth,
            }
            
            # Priorizar sites médicos confiáveis (se não especificado)
            if include_domains is None:
                search_kwargs["include_domains"] = [
                    "pubmed.ncbi.nlm.nih.gov",
                    "uptodate.com",
                    "medscape.com",
                    "nejm.org",
                    "bmj.com",
                    "thelancet.com",
                    "scielo.br",
                    "sciencedirect.com",
                    "mayoclinic.org",
                    "who.int",
                    "cdc.gov",
                    "nih.gov",
                ]
            else:
                search_kwargs["include_domains"] = include_domains

            response = self.client.search(**search_kwargs)
            
            # Formatar resultados
            results = []
            if response and "results" in response:
                for item in response["results"]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "content": item.get("content", ""),
                        "score": item.get("score", 0),
                    })
            
            return results

        except Exception as e:
            print(f"Erro ao buscar na web: {e}")
            return []

    def format_results_for_prompt(self, results: List[Dict[str, Any]]) -> str:
        """
        Formata resultados de busca para inclusão no prompt.

        Args:
            results: Lista de resultados da busca.

        Returns:
            String formatada com os resultados.
        """
        if not results:
            return "Nenhum resultado encontrado na busca web."

        formatted = "🌐 **Informações da Web:**\n\n"
        
        for i, result in enumerate(results, 1):
            formatted += f"**[{i}] {result['title']}**\n"
            formatted += f"🔗 {result['url']}\n"
            formatted += f"{result['content'][:300]}...\n\n"
        
        return formatted

