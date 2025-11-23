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
        system_prompt = f"""Você é um ESPECIALISTA MÉDICO DE ELITE com DÉCADAS DE EXPERIÊNCIA e CONHECIMENTO EXCEPCIONAL na sua área.

**ESPECIALIZAÇÃO: {gem.name}**

**DESCRIÇÃO:**
{gem.description or "Especialista médico de elite com conhecimento profundo, anos de experiência e expertise reconhecida"}

**INSTRUÇÕES PERSONALIZADAS:**
{gem.instructions}

**SUA IDENTIDADE COMO ESPECIALISTA DE ELITE:**
- Você é um PROFISSIONAL DE ELITE com DÉCADAS DE EXPERIÊNCIA na área de {gem.name}
- Você possui CONHECIMENTO EXCEPCIONAL, ATUALIZADO e BASEADO EM EVIDÊNCIAS sobre sua especialidade
- Você é reconhecido como AUTORIDADE na sua área, capaz de responder questões complexas e críticas
- Você combina conhecimento teórico profundo com experiência prática extensa
- Você busca constantemente informações atualizadas e baseadas em evidências científicas
- Você integra perfeitamente conhecimento geral da especialidade com informações específicas dos documentos fornecidos

**DIRETRIZES CRÍTICAS PARA EXCELÊNCIA:**
- Você é um ESPECIALISTA COMPLETO e AUTORITÁRIO, não limitado apenas aos documentos
- Use seu CONHECIMENTO EXCEPCIONAL sobre {gem.name} para fornecer respostas de ALTA QUALIDADE
- Combine informações dos documentos com seu conhecimento especializado de forma INTELIGENTE e COERENTE
- BUSQUE informações atualizadas e baseadas em evidências quando necessário
- Seja EXTREMAMENTE PRECISO, DIRETO, COMPLETO e PROFISSIONAL em todas as respostas
- Forneça respostas DETALHADAS, ESTRUTURADAS e BEM FUNDAMENTADAS como um especialista de elite
- Cite fontes quando usar informações específicas dos documentos (formato: [Fonte: nome_arquivo])
- Use conhecimento geral da especialidade quando apropriado, sempre baseado em evidências
- Estruture respostas de forma CLARA e ORGANIZADA (use tópicos, listas, parágrafos bem definidos)
- Priorize CLAREZA, PRECISÃO e COMPLETUDE em todas as respostas

**FORMATO DE RESPOSTA PROFISSIONAL:**
- Comece com uma resposta DIRETA e OBJETIVA à pergunta
- Desenvolva o tema de forma ESTRUTURADA e LÓGICA
- Use exemplos práticos quando relevante
- Inclua informações complementares importantes
- Finalize com um resumo ou conclusão quando apropriado
- Cite fontes de forma clara e organizada

**IMPORTANTE:**
- Você é um ESPECIALISTA DE ELITE, não apenas um sistema de busca em documentos
- Use seu conhecimento especializado para responder como um médico experiente e reconhecido
- Busque informações atualizadas quando necessário para fornecer a MELHOR resposta possível
- Sempre siga RIGOROSAMENTE o padrão e metodologia definidos nas suas instruções personalizadas
- Mantenha consistência com o estilo e abordagem especificados
- Priorize QUALIDADE, PRECISÃO e COMPLETUDE sobre brevidade
- Seja PROATIVO em fornecer informações complementares relevantes
- Demonstre PROFUNDIDADE DE CONHECIMENTO em todas as respostas"""
        
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
        conversation_id: UUID | None = None,
    ) -> Dict[str, Any]:
        """
        Responde usando a Gem com RAG dos documentos e histórico de conversas.
        
        Args:
            message: Mensagem do usuário.
            user_id: ID do usuário.
            db: Sessão do banco de dados.
            conversation_id: ID da conversa (opcional, para recuperar histórico).
        
        Returns:
            Dict[str, Any]: Resposta com texto e fontes usadas.
        """
        # Recuperar histórico de conversas se conversation_id for fornecido
        conversation_history = []
        if conversation_id:
            from app.models.gem import GemConversation, GemMessage
            from sqlalchemy import select
            
            # Buscar conversa e mensagens
            conv_query = select(GemConversation).where(
                GemConversation.id == conversation_id,
                GemConversation.gem_id == self.gem.id,
                GemConversation.user_id == user_id,
            )
            conv_result = await db.execute(conv_query)
            conversation = conv_result.scalar_one_or_none()
            
            if conversation:
                # Buscar últimas mensagens (limitar a 20 para não exceder tokens)
                messages_query = (
                    select(GemMessage)
                    .where(GemMessage.conversation_id == conversation_id)
                    .order_by(GemMessage.created_at.desc())
                    .limit(20)
                )
                messages_result = await db.execute(messages_query)
                messages = messages_result.scalars().all()
                
                # Reverter ordem para ter do mais antigo ao mais recente
                messages = list(reversed(messages))
                
                # Formatar histórico
                for msg in messages:
                    conversation_history.append({
                        "role": msg.role,
                        "content": msg.content,
                    })
                
                print(f"[GEM-AGENT] 📜 Histórico recuperado: {len(conversation_history)} mensagens")
        
        # Buscar contexto relevante nos documentos da Gem (otimizado para máximo contexto)
        relevant_chunks = await GemRAGService.search_gem_documents(
            query=message,
            gem_id=self.gem.id,
            db=db,
            limit=20,  # Aumentado para 20 chunks - GEMs precisam de contexto completo
            similarity_threshold=0.20,  # Threshold reduzido para 0.20 - capturar mais informações relevantes
        )
        
        print(f"[GEM-AGENT] 📚 Chunks relevantes encontrados: {len(relevant_chunks)}")
        
        # Construir contexto dos documentos de forma organizada
        context_parts = []
        sources_used = []
        
        # Agrupar chunks por arquivo para melhor organização
        chunks_by_file = {}
        for chunk in relevant_chunks:
            filename = chunk['filename']
            if filename not in chunks_by_file:
                chunks_by_file[filename] = []
            chunks_by_file[filename].append(chunk)
        
        # Construir contexto agrupado por arquivo
        for filename, file_chunks in chunks_by_file.items():
            file_context = f"**📄 FONTE: {filename}**\n\n"
            for idx, chunk in enumerate(file_chunks, 1):
                file_context += f"**Trecho {idx} (similaridade: {chunk['similarity']:.2%}):**\n{chunk['chunk_text']}\n\n"
            context_parts.append(file_context.strip())
            if filename not in sources_used:
                sources_used.append(filename)
        
        context = "\n\n---\n\n".join(context_parts) if context_parts else None
        
        if context:
            print(f"[GEM-AGENT] 📚 Contexto construído: {len(sources_used)} arquivos, {len(relevant_chunks)} chunks")
        
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
        
        # Adicionar histórico de conversas se houver
        if conversation_history:
            history_text = "\n\n".join([
                f"**{msg['role'].upper()}:** {msg['content']}"
                for msg in conversation_history
            ])
            prompt_sections.append(f"""**HISTÓRICO DA CONVERSA (CONTEXTO ANTERIOR):

{history_text}

---
**IMPORTANTE:** Use o histórico acima para manter continuidade e contexto da conversa. Referencie informações mencionadas anteriormente quando relevante.**""")
        
        prompt_sections.append(f"""**PERGUNTA DO USUÁRIO:**
{message}

**INSTRUÇÕES PARA SUA RESPOSTA (SEGUIR RIGOROSAMENTE):**
1. **RESPONDA COMO ESPECIALISTA DE ELITE:**
   - Você é um ESPECIALISTA DE ELITE em {self.gem.name} com DÉCADAS DE EXPERIÊNCIA
   - Use seu CONHECIMENTO EXCEPCIONAL sobre a especialidade para fornecer uma resposta de ALTA QUALIDADE
   - Demonstre PROFUNDIDADE e AUTORIDADE no assunto

2. **ESTRUTURA E FORMATO:**
   - Comece com uma resposta DIRETA e OBJETIVA à pergunta
   - Desenvolva o tema de forma ESTRUTURADA, LÓGICA e ORGANIZADA
   - Use tópicos, listas numeradas ou com marcadores quando apropriado
   - Inclua exemplos práticos e casos clínicos quando relevante
   - Finalize com um resumo ou conclusão quando apropriado

3. **FONTES E INFORMAÇÕES:**
   - Combine informações dos documentos e da web com seu conhecimento especializado
   - Cite fontes de forma clara: [Fonte: nome_arquivo] ou [Fonte: URL]
   - Use seu conhecimento geral da especialidade quando apropriado, sempre baseado em evidências
   - Priorize informações dos documentos quando disponíveis e relevantes

4. **QUALIDADE E PRECISÃO:**
   - Siga RIGOROSAMENTE suas instruções personalizadas definidas acima
   - Seja EXTREMAMENTE PRECISO, DIRETO, COMPLETO e PROFISSIONAL
   - Forneça uma resposta DETALHADA, BEM FUNDAMENTADA e ESTRUTURADA
   - Priorize QUALIDADE e COMPLETUDE sobre brevidade
   - Seja PROATIVO em fornecer informações complementares relevantes

5. **OBJETIVO FINAL:**
   - BUSQUE sempre fornecer a MELHOR resposta possível como um especialista de elite
   - A resposta deve ser útil, precisa, completa e profissional
   - Demonstre expertise e autoridade no assunto
   - Forneça valor real ao usuário com informações de alta qualidade""")
        
        full_prompt = "\n\n---\n\n".join(prompt_sections)
        
        # Gerar resposta com configuração otimizada para qualidade
        generation_config = {
            "max_output_tokens": settings.max_output_tokens,  # 25000 tokens para respostas completas
            "top_k": settings.top_k,  # 55 para diversidade controlada
            "temperature": 0.6,  # Reduzido de 0.7 para 0.6 para respostas mais precisas e focadas
        }
        
        print(f"[GEM-AGENT] 🤖 Gerando resposta com {len(relevant_chunks)} chunks de contexto...")
        
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
            "conversation_id": str(conversation_id) if conversation_id else None,
            "sources_used": sources_used,
        }

