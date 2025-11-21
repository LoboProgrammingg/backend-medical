"""Agente especializado que usa Gem para responder."""

from typing import Any, Dict
from uuid import UUID

import google.generativeai as genai
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base_agent import BaseAgent
from app.config.settings import settings
from app.models.gem import Gem
from app.services.gem_rag_service import GemRAGService
from app.utils.web_search import WebSearchTool

# Configurar API do Google
genai.configure(api_key=settings.google_api_key)


class GemAgent(BaseAgent):
    """Agente especializado que usa uma Gem específica para responder."""

    def __init__(self, gem: Gem):
        """
        Inicializa o Gem Agent.
        
        Args:
            gem: Instância da Gem a ser usada.
        """
        system_prompt = f"""Você é um ESPECIALISTA MÉDICO PROFISSIONAL com ANOS DE EXPERIÊNCIA e CONHECIMENTO PROFUNDO na sua área.

**ESPECIALIZAÇÃO: {gem.name}**

**DESCRIÇÃO:**
{gem.description or "Especialista médico com conhecimento profundo e anos de experiência"}

**INSTRUÇÕES PERSONALIZADAS:**
{gem.instructions}

**SUA IDENTIDADE COMO ESPECIALISTA:**
- Você é um PROFISSIONAL com ANOS DE EXPERIÊNCIA na área de {gem.name}
- Você possui CONHECIMENTO PROFUNDO e ATUALIZADO sobre sua especialidade
- Você é capaz de responder perguntas complexas com base no seu conhecimento especializado
- Você busca informações atualizadas quando necessário para fornecer respostas precisas
- Você combina conhecimento geral da especialidade com informações específicas dos documentos fornecidos

**DIRETRIZES CRÍTICAS:**
- Você é um ESPECIALISTA COMPLETO, não limitado apenas aos documentos
- Use seu CONHECIMENTO PROFUNDO sobre {gem.name} para responder
- Combine informações dos documentos com seu conhecimento especializado
- BUSQUE informações atualizadas quando necessário para responder perfeitamente
- Seja PRECISO, DIRETO e PROFISSIONAL em todas as respostas
- Forneça respostas COMPLETAS e DETALHADAS como um especialista experiente
- Cite fontes quando usar informações específicas dos documentos
- Use conhecimento geral da especialidade quando apropriado

**IMPORTANTE:**
- Você é um ESPECIALISTA PROFISSIONAL, não apenas um sistema de busca em documentos
- Use seu conhecimento especializado para responder como um médico experiente
- Busque informações atualizadas quando necessário para fornecer a melhor resposta
- Sempre siga o padrão e metodologia definidos nas suas instruções personalizadas
- Mantenha consistência com o estilo e abordagem especificados
- Priorize ser um ESPECIALISTA COMPLETO sobre ser limitado a documentos"""
        
        super().__init__(
            name=f"Gem: {gem.name}",
            system_prompt=system_prompt,
        )
        self.gem = gem
        self.web_search = WebSearchTool()

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa a lógica do agente (método abstrato obrigatório).
        
        Args:
            state: Estado atual do grafo.
        
        Returns:
            Dict[str, Any]: Estado atualizado.
        """
        # Este método é obrigatório da classe base, mas não é usado para Gems
        # O método chat() é usado diretamente
        return {
            "response": "Gem Agent executado",
            "gem_id": str(self.gem.id),
            "gem_name": self.gem.name,
        }

    async def chat(
        self,
        message: str,
        user_id: UUID,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Responde usando a Gem com RAG dos documentos.
        
        Args:
            message: Mensagem do usuário.
            user_id: ID do usuário.
            db: Sessão do banco de dados.
        
        Returns:
            Dict[str, Any]: Resposta com texto e fontes usadas.
        """
        # Buscar contexto relevante nos documentos da Gem
        relevant_chunks = await GemRAGService.search_gem_documents(
            query=message,
            gem_id=self.gem.id,
            db=db,
            limit=5,
            similarity_threshold=0.3,
        )
        
        # Construir contexto dos documentos
        context_parts = []
        sources_used = []
        
        for chunk in relevant_chunks:
            context_parts.append(f"**Fonte: {chunk['filename']}**\n{chunk['chunk_text']}")
            if chunk['filename'] not in sources_used:
                sources_used.append(chunk['filename'])
        
        context = "\n\n---\n\n".join(context_parts) if context_parts else None
        
        # Buscar informações na web se necessário (sempre para garantir respostas completas)
        web_context = None
        if self.web_search.is_available():
            try:
                # Buscar informações atualizadas sobre a especialidade
                search_query = f"{message} {self.gem.name} medicina"
                web_results = await self.web_search.search(search_query, max_results=3)
                if web_results:
                    web_context = self.web_search.format_results_for_prompt(web_results)
                    # Adicionar URLs às fontes
                    for result in web_results:
                        if result.get('url') and result['url'] not in sources_used:
                            sources_used.append(result['url'])
            except Exception as e:
                print(f"⚠️ Erro ao buscar na web: {e}")
        
        # Construir prompt completo incluindo system_prompt (instruções da Gem)
        prompt_sections = [self.system_prompt]
        
        if context:
            prompt_sections.append(f"""**INFORMAÇÕES DOS DOCUMENTOS DA GEM:**

{context}""")
        
        if web_context:
            prompt_sections.append(f"""**INFORMAÇÕES ATUALIZADAS DA WEB:**

{web_context}""")
        
        prompt_sections.append(f"""**PERGUNTA DO USUÁRIO:**
{message}

**RESPONDA COMO ESPECIALISTA:**
- Você é um ESPECIALISTA PROFISSIONAL em {self.gem.name} com ANOS DE EXPERIÊNCIA
- Use seu CONHECIMENTO PROFUNDO sobre a especialidade para responder
- Combine informações dos documentos e da web com seu conhecimento especializado
- Siga RIGOROSAMENTE suas instruções personalizadas definidas acima
- Seja PRECISO, DIRETO, COMPLETO e PROFISSIONAL
- Forneça uma resposta DETALHADA como um especialista experiente
- Cite as fontes quando usar informações específicas
- Use seu conhecimento geral da especialidade quando apropriado
- BUSQUE sempre fornecer a MELHOR resposta possível como um profissional experiente""")
        
        full_prompt = "\n\n---\n\n".join(prompt_sections)
        
        # Gerar resposta
        generation_config = {
            "max_output_tokens": settings.max_output_tokens,
            "top_k": settings.top_k,
            "temperature": 0.7,
        }
        
        model = genai.GenerativeModel(
            settings.gemini_model,
            generation_config=generation_config,
        )
        
        response = model.generate_content(full_prompt)
        response_text = response.text.strip()
        
        return {
            "response": response_text,
            "gem_id": str(self.gem.id),
            "gem_name": self.gem.name,
            "sources_used": sources_used,
        }

