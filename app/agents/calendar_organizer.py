"""Calendar Organizer Agent - Organiza calendário médico e plantões."""

import json
import re
from datetime import date, datetime, time
from typing import Any, Dict, List
from uuid import UUID

import google.generativeai as genai
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base_agent import BaseAgent
from app.config.settings import settings


class CalendarOrganizerAgent(BaseAgent):
    """Agente que organiza calendário de plantões e turnos médicos."""

    SYSTEM_PROMPT = """Você é uma especialista em organização de calendários médicos e gestão de plantões.

**SUA FUNÇÃO CRÍTICA:**
Extrair e organizar calendários médicos de PDFs com PRECISÃO ABSOLUTA. Um erro pode fazer um médico perder um plantão ou ir trabalhar no dia errado!

**CAPACIDADES:**
- Extrair dados de calendários em PDF com precisão
- Identificar grupo, nome e posição na lista (ex: Grupo 7, Tatiana Minakami, A1)
- Distinguir dias normais de trabalho (Semana 1, Semana 2, etc.) por dias da semana
- Identificar plantões específicos (onde aparece o grupo e posição, ex: (7) A1)
- Extrair datas, horários, locais e tipos de plantão com precisão

**FORMATO DE EXTRAÇÃO (JSON):**

Você DEVE retornar um JSON estruturado com esta estrutura EXATA:

{
  "group_number": 7,
  "name": "Tatiana Minakami",
  "position": "A1",
  "start_date": "2025-10-27",
  "end_date": "2025-12-21",
  "work_days": [
    {
      "week": 1,
      "day_of_week": "Seg",
      "date": "2025-10-27",
      "type": "work",
      "location": "UPA1",
      "shift_type": "Sala Vermelha",
      "start_time": "07:00",
      "end_time": "19:00"
    }
  ],
  "on_call_shifts": [
    {
      "date": "2025-10-29",
      "day_of_week": "Qua",
      "week": 1,
      "location": "UPA1",
      "shift_type": "Plantão Cinderela",
      "start_time": "19:00",
      "end_time": "23:00"
    }
  ]
}

**REGRAS CRÍTICAS:**
1. PRECISÃO ABSOLUTA: Todas as datas devem estar corretas
2. IDENTIFICAÇÃO: Encontrar grupo, nome e posição (A1, B2, etc.) no PDF
3. DIAS DE TRABALHO: Extrair todos os dias normais organizados por semana e dia da semana
4. PLANTÕES: Extrair APENAS onde aparece o grupo e posição (ex: (7) A1)
5. VALIDAÇÃO: Verificar se todas as datas estão no período correto
6. SEM ERROS: Um erro pode causar problemas graves!

**DIRETRIZES:**
- Seja EXTREMAMENTE precisa
- Valide todas as datas
- Confirme grupo, nome e posição antes de extrair
- Organize por semanas e dias da semana claramente"""

    def __init__(self):
        """Inicializa o Calendar Organizer Agent."""
        super().__init__(
            name="Calendar Organizer",
            system_prompt=self.SYSTEM_PROMPT,
        )

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa organização de calendário.

        Args:
            state: Estado atual contendo:
                - calendar_text: Texto do calendário (bruto/confuso)
                - month: Mês de referência (opcional)
                - year: Ano de referência (opcional)

        Returns:
            Dict[str, Any]: Estado atualizado com calendário organizado.
        """
        calendar_text = state["calendar_text"]
        month = state.get("month", datetime.now().month)
        year = state.get("year", datetime.now().year)

        organization_prompt = f"""Analise e organize o seguinte calendário médico:

**MÊS/ANO:** {month}/{year}

**CALENDÁRIO ORIGINAL (possivelmente confuso):**
{calendar_text}

**TAREFAS:**
1. Identificar e categorizar cada dia
2. Detectar plantões vs turnos regulares
3. Identificar folgas e descansos
4. Alertar sobre possíveis conflitos ou sobrecarga
5. Apresentar de forma clara e visual

Organize em formato semanal com legendas claras."""

        organized = await self.generate_response(organization_prompt)

        state["organized_calendar"] = organized
        state["agent_used"] = self.name

        return state

    async def analyze_workload(
        self,
        calendar_text: str,
        period_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Analisa carga de trabalho em um período.

        Args:
            calendar_text: Texto do calendário.
            period_days: Número de dias do período.

        Returns:
            Dict[str, Any]: Análise de carga de trabalho.
        """
        prompt = f"""Analise a carga de trabalho neste calendário de {period_days} dias:

{calendar_text}

**FORNEÇA:**
1. 📊 **Estatísticas:**
   - Total de turnos regulares
   - Total de plantões
   - Total de folgas
   - Horas totais trabalhadas (estimativa)

2. ⚠️ **Alertas de Sobrecarga:**
   - Semanas críticas (>60h)
   - Plantões consecutivos
   - Falta de descanso adequado

3. 💡 **Recomendações:**
   - Ajustes sugeridos
   - Prioridades de descanso
   - Otimizações possíveis

4. 🎯 **Score de Saúde:** (0-100)
   - Avaliação geral da escala

Seja objetiva e baseada em boas práticas médicas."""

        analysis = await self.generate_response(prompt)

        return {
            "analysis": analysis,
            "period_days": period_days,
            "agent": self.name,
        }

    async def extract_calendar_from_pdf(
        self,
        pdf_text: str,
        group_number: int,
        name: str,
        position: str,
    ) -> Dict[str, Any]:
        """
        Extrai calendário de um PDF com precisão absoluta.
        
        Args:
            pdf_text: Texto extraído do PDF
            group_number: Número do grupo (ex: 7)
            name: Nome da pessoa (ex: Tatiana Minakami)
            position: Posição na lista (ex: A1)
            
        Returns:
            Dict com calendário estruturado
        """
        import asyncio
        from google.api_core import exceptions as google_exceptions
        
        # Configurar Gemini
        genai.configure(api_key=settings.google_api_key)
        generation_config = {
            "max_output_tokens": settings.max_output_tokens,
            "top_k": settings.top_k,
            "temperature": 0.1,  # Baixa temperatura para precisão
        }
        model = genai.GenerativeModel(
            settings.gemini_model,
            generation_config=generation_config,
        )
        
        prompt = f"""Você é uma especialista em extrair calendários médicos de PDFs com PRECISÃO ABSOLUTA.

**INFORMAÇÕES DO USUÁRIO:**
- Grupo: {group_number}
- Nome: {name}
- Posição na lista: {position}

**TEXTO DO PDF:**
{pdf_text[:15000]}  # Limitar para reduzir tempo de processamento

**SUA TAREFA CRÍTICA:**

1. **IDENTIFICAR O USUÁRIO NO CALENDÁRIO:**
   - Procurar pelo grupo {group_number} e posição {position} (ex: (7) A1)
   - Procurar pelo nome "{name}"
   - Confirmar que é a pessoa correta

2. **EXTRAIR DIAS DE TRABALHO NORMAL:**
   - Procurar por "Semana 1", "Semana 2", etc.
   - Identificar os dias da semana (Seg, Ter, Qua, Qui, Sex, Sáb, Dom)
   - Extrair datas, locais, horários e tipos de turno
   - Organizar por semana e dia da semana

3. **EXTRAIR PLANTÕES:**
   - Procurar APENAS onde aparece ({group_number}) {position}
   - Extrair data, local, tipo de plantão, horários
   - Confirmar que é realmente um plantão

4. **EXTRAIR PRECEPTOR RESPONSÁVEL:**
   - Identificar o preceptor responsável de cada semana
   - Cada semana pode ter um preceptor diferente
   - Procurar por informações como "Preceptor", "Responsável", nomes de médicos/preceptores
   - Associar o preceptor à semana correspondente

5. **RETORNAR JSON ESTRUTURADO:**

Você DEVE retornar APENAS um JSON válido com esta estrutura:

{{
  "group_number": {group_number},
  "name": "{name}",
  "position": "{position}",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "work_days": [
    {{
      "week": 1,
      "day_of_week": "Seg",
      "date": "YYYY-MM-DD",
      "type": "work",
      "location": "UPA1",
      "shift_type": "Sala Vermelha",
      "start_time": "HH:MM",
      "end_time": "HH:MM",
      "preceptor": "Nome do Preceptor"
    }}
  ],
  "on_call_shifts": [
    {{
      "date": "YYYY-MM-DD",
      "day_of_week": "Qua",
      "week": 1,
      "location": "UPA1",
      "shift_type": "Plantão Cinderela",
      "start_time": "HH:MM",
      "end_time": "HH:MM",
      "preceptor": "Nome do Preceptor"
    }}
  ]
}}

**REGRAS CRÍTICAS:**
- PRECISÃO ABSOLUTA: Todas as datas devem estar corretas
- VALIDAÇÃO: Verificar se as datas estão no período do calendário
- SEM ERROS: Um erro pode fazer o médico perder um plantão!
- APENAS JSON: Retorne APENAS o JSON, sem texto adicional
- DATAS: Use formato YYYY-MM-DD
- HORÁRIOS: Use formato HH:MM (24h)

**RESPONDA APENAS COM O JSON, SEM TEXTO ADICIONAL:**"""

        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"[CALENDAR-EXTRACT] Tentativa {attempt + 1}/{max_retries} - Enviando para Gemini...")
                # Adicionar timeout para evitar espera infinita
                import asyncio
                loop = asyncio.get_event_loop()
                
                # Wrapper para capturar exceções
                def generate_sync():
                    try:
                        return model.generate_content(prompt)
                    except Exception as e:
                        print(f"[CALENDAR-EXTRACT] Erro na geração: {e}")
                        raise
                
                response = await asyncio.wait_for(
                    loop.run_in_executor(None, generate_sync),
                    timeout=90.0  # 90 segundos máximo
                )
                
                if not response or not hasattr(response, 'text'):
                    raise ValueError("Resposta vazia do Gemini")
                
                response_text = response.text.strip()
                print(f"[CALENDAR-EXTRACT] Resposta recebida: {len(response_text)} caracteres")
                
                # Limpar resposta (remover markdown code blocks se houver)
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0].strip()
                
                # Parsear JSON
                calendar_data = json.loads(response_text)
                
                # Validar estrutura
                if not isinstance(calendar_data, dict):
                    raise ValueError("Resposta não é um dicionário")
                
                if "work_days" not in calendar_data:
                    calendar_data["work_days"] = []
                if "on_call_shifts" not in calendar_data:
                    calendar_data["on_call_shifts"] = []
                
                return calendar_data
                
            except json.JSONDecodeError as e:
                print(f"❌ Erro ao parsear JSON (tentativa {attempt + 1}): {e}")
                print(f"Resposta recebida: {response_text[:500]}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                else:
                    raise ValueError(f"Falha ao extrair calendário: JSON inválido. Resposta: {response_text[:500]}")
            except google_exceptions.ResourceExhausted:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 2
                    print(f"⚠️ Rate limit. Aguardando {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    raise
            except Exception as e:
                print(f"❌ Erro ao extrair calendário (tentativa {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                else:
                    raise

    async def suggest_study_schedule(
        self,
        calendar_text: str,
        study_hours_per_week: int = 10,
    ) -> Dict[str, Any]:
        """
        Sugere horários de estudo baseado no calendário de trabalho.

        Args:
            calendar_text: Calendário de trabalho/plantões.
            study_hours_per_week: Meta de horas de estudo semanal.

        Returns:
            Dict[str, Any]: Sugestão de cronograma de estudos.
        """
        prompt = f"""Com base no calendário de trabalho abaixo, sugira um cronograma de estudos viável:

**CALENDÁRIO DE TRABALHO:**
{calendar_text}

**META:** {study_hours_per_week} horas de estudo por semana

**FORNEÇA:**
1. 📚 **Cronograma Semanal de Estudos:**
   - Dias e horários ideais
   - Duração sugerida por sessão
   - Tipo de estudo (leitura, prática, revisão)

2. 🎯 **Estratégias:**
   - Como aproveitar intervalos
   - Quando fazer revisões rápidas
   - Momentos de estudo mais intenso

3. ⚖️ **Balanço Vida-Estudo-Trabalho:**
   - Reservar tempo para descanso
   - Equilibrar carga total

Seja realista e considere a fadiga de plantões."""

        schedule = await self.generate_response(prompt)

        return {
            "study_schedule": schedule,
            "target_hours": study_hours_per_week,
            "agent": self.name,
        }

