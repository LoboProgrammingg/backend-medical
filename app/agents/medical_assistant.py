"""Medical Assistant Agent - Assistente médica conversacional."""

import asyncio
from typing import Any, Dict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base_agent import BaseAgent
from app.services.rag_service import RAGService
from app.services.hybrid_rag_service import HybridRAGService
from app.utils.web_search import WebSearchTool
from app.config.settings import settings


class MedicalAssistantAgent(BaseAgent):
    """Agente assistente médica conversacional."""

    SYSTEM_PROMPT = """Você é uma assistente médica especializada, prática e resolutiva, desenvolvida para apoiar estudantes de medicina.

**SUA IDENTIDADE:**
- Nome: Amorinha (assistente médica pessoal)
- Especialidade: Medicina geral, com foco em apoio acadêmico e clínico
- Tom: Profissional, direto, prático e resolutivo
- Objetivo: Fornecer respostas médicas práticas, diretas e úteis

**SUAS CAPACIDADES:**
1. Fornecer prescrições médicas práticas quando solicitado
2. Responder perguntas médicas com base nas anotações, documentos e fontes oficiais
3. Buscar informações atualizadas na internet quando necessário
4. Dar respostas diretas, práticas e resolutivas
5. Fornecer dosagens, posologias e condutas específicas
6. Citar as fontes usadas

**DIRETRIZES CRÍTICAS:**
- SEJA DIRETO E PRÁTICO: Quando o usuário pedir uma prescrição, conduta ou tratamento, FORNEÇA DIRETAMENTE
- NÃO SEJA EXCESSIVAMENTE CAUTELOSA: Dê respostas práticas baseadas nas fontes disponíveis
- FORNEÇA PRESCRIÇÕES COMPLETAS: Inclua medicamentos, dosagens, posologias e orientações
- PRIORIDADE 1: Use as anotações do usuário como fonte primária
- PRIORIDADE 2: Use documentos do usuário (PDFs)
- PRIORIDADE 3: Use protocolos oficiais (PCDT, diretrizes)
- PRIORIDADE 4: Use informações da web (quando necessário)
- SEMPRE forneça respostas práticas e aplicáveis
- Cite as fontes usadas

**EXEMPLOS DE RESPOSTAS PRÁTICAS:**

Usuário: "Me fale como que eu receitaria um paciente que está sentindo muito enjoo e dor de cabeça forte"
Você: "**PRESCRIÇÃO PARA ENJOO E DOR DE CABEÇA FORTE:**

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

*Fonte: Protocolos de atendimento de urgência e suas anotações sobre sintomas comuns*"

Usuário: "Como tratar ICC?"
Você: "**TRATAMENTO DE INSUFICIÊNCIA CARDÍACA CONGESTIVA:**

📋 **Farmacológico:**
- **Enalapril 10mg** - 1 comprimido 2x/dia (IECA - primeira linha)
- **Carvedilol 25mg** - 1 comprimido 2x/dia (Beta-bloqueador)
- **Furosemida 40mg** - 1 comprimido pela manhã (Diurético)

📋 **Não-farmacológico:**
- Restrição de sódio <2g/dia
- Controle de peso diário
- Atividade física moderada (após estabilização)

*Fonte: Suas anotações sobre Cardiologia - ICC*"

**IMPORTANTE:**
- SEMPRE responda em português brasileiro (pt-BR)
- Seja DIRETO, PRÁTICO e RESOLUTIVO
- Quando pedir prescrição, FORNEÇA prescrição completa
- Priorize informações das anotações/documentos do usuário
- Use informações de fontes oficiais quando necessário
- NÃO seja excessivamente cautelosa - seja prática e útil"""

    def __init__(self):
        """Inicializa o Medical Assistant Agent."""
        super().__init__(
            name="Medical Assistant",
            system_prompt=self.SYSTEM_PROMPT,
        )
        self.web_search = WebSearchTool()

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa o agente de assistência médica.

        Args:
            state: Estado atual contendo:
                - question: Pergunta do usuário
                - user_id: ID do usuário
                - db: Sessão do banco
                - context_limit: Limite de contexto (opcional)

        Returns:
            Dict[str, Any]: Estado atualizado com answer e context_used.
        """
        question = state["question"]
        user_id = state["user_id"]
        db: AsyncSession = state["db"]
        context_limit = state.get("context_limit", 3)

        # Buscar contexto relevante das anotações
        rag_result = await RAGService.ask_with_context(
            question=question,
            user_id=user_id,
            db=db,
            context_limit=context_limit,
        )

        # Atualizar estado
        state["answer"] = rag_result["answer"]
        state["context_used"] = rag_result["context_used"]
        state["has_context"] = rag_result["has_context"]
        state["agent_used"] = self.name

        return state

    async def chat(
        self,
        message: str,
        user_id: UUID,
        db: AsyncSession,
        conversation_history: list[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Interface de chat conversacional.

        Args:
            message: Mensagem do usuário.
            user_id: ID do usuário.
            db: Sessão do banco.
            conversation_history: Histórico da conversa (opcional).

        Returns:
            Dict[str, Any]: Resposta do agente.
        """
        # 🆕 USAR HYBRID RAG: Buscar em anotações + documentos user + documentos oficiais
        hybrid_result = await HybridRAGService.ask_with_hybrid_rag(
            question=message,
            user_id=user_id,
            db=db,
        )

        # Se não encontrou contexto suficiente, buscar na web
        if not hybrid_result["has_context"]:
            try:
                print(f"🌐 Nenhum contexto encontrado. Buscando na web: {message}")
                web_results = await self.web_search.search(message, max_results=3)
                if web_results:
                    web_context = self.web_search.format_results_for_prompt(web_results)
                    
                    # Gerar resposta com web context - DIRETO E PRÁTICO
                    web_prompt = f"""Você é uma assistente médica especializada, PRÁTICA e RESOLUTIVA.

**SUA MISSÃO:** Fornecer respostas médicas DIRETAS, PRÁTICAS e COMPLETAS.

**PERGUNTA DO USUÁRIO:**
{message}

**INFORMAÇÕES DA WEB:**
{web_context}

**INSTRUÇÕES CRÍTICAS:**

1. **SEJA DIRETO E PRÁTICO:**
   - Se o usuário pedir uma PRESCRIÇÃO, forneça prescrição COMPLETA com medicamentos, dosagens e posologias
   - Se pedir uma CONDUTA, forneça conduta detalhada e prática
   - Se pedir um TRATAMENTO, forneça tratamento completo e aplicável

2. **NÃO SEJA EXCESSIVAMENTE CAUTELOSA:**
   - Dê respostas práticas baseadas nas informações da web
   - Não fique apenas explicando "limitações" - FORNEÇA SOLUÇÕES
   - Seja resolutiva e útil

3. **FORMATO DE RESPOSTA:**
   - Use Markdown para estruturação
   - Se for prescrição, use formato: **Medicamento** - Dosagem - Posologia
   - Inclua orientações práticas
   - Cite as fontes da web (🌐 URLs)

4. **EXEMPLO DE PRESCRIÇÃO:**
   Quando pedir prescrição, responda assim:
   ```
   **PRESCRIÇÃO:**
   
   📋 **Medicamentos:**
   1. **Paracetamol 750mg** - 1 comprimido a cada 8 horas
   2. **Metoclopramida 10mg** - 1 comprimido a cada 8 horas
   
   📋 **Orientações:**
   - Repouso relativo
   - Hidratação abundante
   - Retornar se piorar
   ```

**RESPONDA AGORA DE FORMA DIRETA, PRÁTICA E COMPLETA. Use as informações da web para fornecer uma resposta útil e resolutiva. Cite as fontes (🌐 URLs).**"""
                    
                    response = await self.generate_response(web_prompt)
                    hybrid_result["answer"] = response
                    hybrid_result["has_context"] = True
                    print(f"✅ Resposta gerada com {len(web_results)} fontes da web")
            except Exception as e:
                print(f"❌ Erro ao buscar na web: {e}")

        return {
            "response": hybrid_result["answer"],
            "context_used": hybrid_result["context_used"],
            "has_context": hybrid_result["has_context"],
            "agent": self.name,
        }

    async def analyze_file(
        self,
        file_content: bytes,
        file_type: str,
        question: str,
        user_id: UUID,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Analisa uma imagem ou arquivo e responde baseado no conteúdo.
        
        Args:
            file_content: Conteúdo do arquivo em bytes
            file_type: Tipo do arquivo (image/jpeg, image/png, application/pdf, etc.)
            question: Pergunta do usuário sobre o arquivo
            user_id: ID do usuário
            db: Sessão do banco
        
        Returns:
            Dict com resposta e informações do arquivo
        """
        import base64
        import google.generativeai as genai
        from google.api_core import exceptions as google_exceptions
        import asyncio
        
        # Configurar Gemini para análise multimodal
        genai.configure(api_key=settings.google_api_key)
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
        
        # Preparar prompt
        prompt = f"""Você é uma assistente médica especializada em análise de imagens e documentos médicos.

**SUA MISSÃO:** Analisar o arquivo enviado e responder a pergunta do usuário de forma DIRETA, PRÁTICA, COMPLETA e DETALHADA.

**PERGUNTA DO USUÁRIO:**
{question}

**INSTRUÇÕES CRÍTICAS:**

1. **ANÁLISE COMPLETA:**
   - Analise TODO o conteúdo do arquivo, não apenas a parte que responde diretamente à pergunta
   - Se for um calendário, escala ou documento organizacional, inclua TODAS as informações relevantes
   - Se for uma imagem médica (raio-X, ECG, exame de sangue, etc.), descreva TUDO que você vê em detalhes
   - Se for um documento, extraia TODAS as informações relevantes, não apenas as que respondem à pergunta

2. **RESPOSTA COMPLETA:**
   - Responda a pergunta do usuário de forma DIRETA e PRÁTICA
   - MAS TAMBÉM forneça TODO o contexto relevante do arquivo
   - Se a pergunta pede informações específicas (ex: "meus dias de trabalho"), forneça:
     * A resposta direta (os dias específicos)
     * TODO o contexto relacionado (todos os grupos, todas as semanas, todas as informações do calendário)
     * Detalhes adicionais que possam ser úteis

3. **FORMATO E ESTRUTURA:**
   - Use Markdown para estruturar a resposta
   - Organize em seções claras (ex: "Resposta Direta", "Contexto Completo", "Detalhes Adicionais")
   - Use listas, tabelas e formatação para facilitar a leitura
   - Seja específico e técnico quando apropriado

4. **EXEMPLO DE RESPOSTA COMPLETA:**
   Se a pergunta for "Quais são meus dias de trabalho?", a resposta deve incluir:
   - ✅ Seus dias específicos de trabalho (resposta direta)
   - ✅ TODA a escala do calendário (todos os grupos, todas as semanas)
   - ✅ Informações sobre locais, horários, tipos de plantão
   - ✅ Qualquer informação adicional relevante do documento

**IMPORTANTE:** NÃO seja limitada na resposta. Forneça TODO o contexto relevante do arquivo, não apenas a resposta mínima à pergunta.

**RESPONDA AGORA COM TODOS OS DETALHES:**"""

        try:
            # Preparar conteúdo para Gemini
            if file_type.startswith("image/"):
                # É uma imagem - usar análise visual
                from PIL import Image
                import io
                
                # Abrir imagem
                image = Image.open(io.BytesIO(file_content))
                
                # Prompt melhorado para imagens (calendários, escalas, etc.)
                image_prompt = f"""{prompt}

**INSTRUÇÕES ESPECÍFICAS PARA ANÁLISE DE IMAGEM:**
1. Analise TODO o conteúdo visível na imagem
2. Se for um calendário, escala ou documento organizacional:
   - Leia TODAS as informações visíveis (todos os grupos, todas as semanas, todos os horários)
   - Identifique padrões e estruturas
   - Extraia TODAS as informações relevantes, não apenas as que respondem à pergunta
3. Se for uma imagem médica (raio-X, ECG, exame):
   - Descreva TUDO que você vê em detalhes
   - Inclua medidas, localizações, características
4. Organize a resposta em seções claras com Markdown
5. Forneça TODO o contexto relevante, não apenas a resposta mínima

**ANALISE A IMAGEM AGORA E FORNEÇA UMA RESPOSTA COMPLETA COM TODO O CONTEXTO:**"""
                
                # Gerar resposta com imagem
                max_retries = 3
                response = None
                for attempt in range(max_retries):
                    try:
                        response = model.generate_content([image_prompt, image])
                        break
                    except google_exceptions.ResourceExhausted:
                        if attempt < max_retries - 1:
                            wait_time = (2 ** attempt) * 2
                            print(f"⚠️ Rate limit. Aguardando {wait_time}s...")
                            await asyncio.sleep(wait_time)
                        else:
                            return {
                                "response": "Desculpe, estou temporariamente sobrecarregada. Tente novamente em alguns segundos.",
                                "has_context": False,
                                "agent": self.name,
                            }
                    except Exception as e:
                        print(f"❌ Erro ao processar imagem: {e}")
                        if attempt == max_retries - 1:
                            raise
                        await asyncio.sleep(2)
                
                if not response:
                    raise Exception("Falha ao gerar resposta")
                
                answer = response.text
                
            elif file_type == "application/pdf":
                # É um PDF - extrair texto primeiro
                from app.utils.pdf_processor import PDFProcessor
                from pathlib import Path
                import tempfile
                
                # Salvar temporariamente
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(file_content)
                    tmp_path = Path(tmp.name)
                
                try:
                    # Extrair texto do PDF
                    pdf_text = PDFProcessor.extract_text_from_pdf(tmp_path)
                    
                    # Adicionar TODO o texto do PDF (aumentar limite para contexto completo)
                    # Limitar a 15000 caracteres para não exceder tokens, mas priorizar contexto completo
                    pdf_text_limited = pdf_text[:15000] if len(pdf_text) > 15000 else pdf_text
                    
                    enhanced_prompt = f"""{prompt}

**CONTEÚDO COMPLETO DO PDF:**
{pdf_text_limited}

**INSTRUÇÕES ESPECÍFICAS PARA ESTA ANÁLISE:**
1. Analise TODO o conteúdo do PDF acima
2. Responda a pergunta do usuário de forma DIRETA
3. MAS TAMBÉM forneça TODO o contexto relevante do documento
4. Se for um calendário ou escala, inclua TODAS as informações (todos os grupos, todas as semanas, todos os horários)
5. Organize a resposta em seções: "Resposta Direta", "Contexto Completo", "Detalhes Adicionais"
6. Use formatação Markdown (listas, tabelas, negrito) para facilitar a leitura

**RESPONDA AGORA COM TODO O CONTEXTO RELEVANTE:**"""
                    
                    # Gerar resposta
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            response = model.generate_content(enhanced_prompt)
                            break
                        except google_exceptions.ResourceExhausted:
                            if attempt < max_retries - 1:
                                wait_time = (2 ** attempt) * 2
                                await asyncio.sleep(wait_time)
                            else:
                                return {
                                    "response": "Desculpe, estou temporariamente sobrecarregada. Tente novamente em alguns segundos.",
                                    "has_context": False,
                                    "agent": self.name,
                                }
                    
                    answer = response.text
                finally:
                    # Remover arquivo temporário
                    if tmp_path.exists():
                        tmp_path.unlink()
            else:
                # Outros tipos de arquivo - tentar como texto
                try:
                    file_text = file_content.decode('utf-8')
                    # Aumentar limite para contexto completo
                    file_text_limited = file_text[:15000] if len(file_text) > 15000 else file_text
                    
                    enhanced_prompt = f"""{prompt}

**CONTEÚDO COMPLETO DO ARQUIVO:**
{file_text_limited}

**INSTRUÇÕES ESPECÍFICAS PARA ESTA ANÁLISE:**
1. Analise TODO o conteúdo do arquivo acima
2. Responda a pergunta do usuário de forma DIRETA
3. MAS TAMBÉM forneça TODO o contexto relevante do documento
4. Se for um calendário ou escala, inclua TODAS as informações (todos os grupos, todas as semanas, todos os horários)
5. Organize a resposta em seções: "Resposta Direta", "Contexto Completo", "Detalhes Adicionais"
6. Use formatação Markdown (listas, tabelas, negrito) para facilitar a leitura

**RESPONDA AGORA COM TODO O CONTEXTO RELEVANTE:**"""
                    
                    response = model.generate_content(enhanced_prompt)
                    answer = response.text
                except:
                    return {
                        "response": f"Desculpe, não consigo processar arquivos do tipo '{file_type}'. Por favor, envie imagens (JPG, PNG) ou PDFs.",
                        "has_context": False,
                        "agent": self.name,
                    }
            
            return {
                "response": answer,
                "has_context": True,
                "agent": self.name,
                "file_type": file_type,
            }
            
        except Exception as e:
            print(f"❌ Erro ao analisar arquivo: {e}")
            import traceback
            traceback.print_exc()
            return {
                "response": f"Desculpe, ocorreu um erro ao analisar o arquivo: {str(e)}",
                "has_context": False,
                "agent": self.name,
            }

    def _format_context(self, context_notes: list[Dict[str, Any]]) -> str:
        """Formata as anotações de contexto."""
        if not context_notes:
            return "(Nenhuma anotação relevante encontrada)"

        formatted = []
        for note in context_notes:
            formatted.append(
                f"• {note['title']} (relevância: {note['similarity']:.0%})"
            )

        return "\n".join(formatted)

