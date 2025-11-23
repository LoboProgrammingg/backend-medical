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
        
        # Obter data e hora atual
        now = datetime.now()
        current_year = now.year
        current_month = now.month
        current_day = now.day
        current_date_str = now.strftime("%d/%m/%Y")
        current_time_str = now.strftime("%H:%M")
        current_day_name = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"][now.weekday()]
        current_weekday_num = now.weekday()  # 0=Segunda, 6=Domingo
        
        prompt = f"""Você é uma especialista em extrair calendários médicos de PDFs ou Excel com PRECISÃO ABSOLUTA.

**REGRA FUNDAMENTAL ABSOLUTA - CONFIE 100% NO DOCUMENTO:**
- O documento JÁ mostra as datas e os dias da semana CORRETOS nas colunas
- NÃO tente validar, verificar ou corrigir usando conhecimento de calendário!
- NÃO use conhecimento sobre qual dia da semana uma data deveria ser!
- NÃO compare com calendários de 2023, 2024, 2025 ou qualquer outro ano!
- Se a data "27/10" está na coluna "SEG", então day_of_week = "Seg" - PONTO FINAL!
- Se a data "03/11" está na coluna "DOM", então day_of_week = "Dom" - PONTO FINAL!
- O documento é a ÚNICA FONTE DA VERDADE - extraia exatamente como está!
- IGNORE completamente qualquer conhecimento sobre calendários que você tenha!
- Se o documento diz que 27/10 é Segunda, então É SEGUNDA, mesmo que você "saiba" que não é!

**INFORMAÇÕES DO USUÁRIO:**
- Grupo: {group_number}
- Nome: {name}
- Posição na lista: {position}

**ESTRUTURA EXATA DO DOCUMENTO:**
O documento tem esta estrutura específica (como planilha):

1. **SEÇÃO "GRUPOS" (topo):**
   - Lista de pessoas organizadas por colunas numeradas (1, 2, 3, 4, 5, 6, 7, 8)
   - Cada pessoa tem um código (ex: A1, B2, C3, etc.)

2. **PARA CADA SEMANA (Semana 1, Semana 2, etc.):**
   
   **a) TABELA "MAPA RECEPTOR":**
   - Colunas: LOCAL | SETOR | HORÁRIO | PRINCIPAL RESPONSÁVEL | SEGUNDA | TERÇA | QUARTA | QUINTA | SEXTA | SÁBADO | DOMINGO
   - Linha de DATAS: Abaixo dos cabeçalhos dos dias, há uma linha com datas DD/MM para cada dia
   - Cada linha representa um turno de trabalho normal
   - Os números nas colunas dos dias (ex: 1, 2, 3, 7, 8) referem-se aos grupos
   
   **b) TABELA "PLANTÃO":**
   - Colunas: PLANTÃO | SEGUNDA | TERÇA | QUARTA | QUINTA | SEXTA | SÁBADO | DOMINGO
   - Cada linha representa um plantão
   - Os plantões aparecem com códigos como ({group_number}) {position} (ex: (7) A1) na COLUNA do dia correspondente
   - **CRÍTICO:** O dia da semana do plantão é determinado pela COLUNA onde o código aparece, não pelo texto ao redor!
   - Exemplo: Se (7) A1 aparece na coluna "DOMINGO", então day_of_week = "Dom", mesmo que o texto mostre outra coisa antes

**TEXTO DO DOCUMENTO (PDF ou Excel extraído):**
{pdf_text[:20000]}  # Limitar para reduzir tempo de processamento (aumentado para melhor precisão)

**SUA TAREFA CRÍTICA:**

1. **IDENTIFICAR O USUÁRIO NO CALENDÁRIO:**
   - Procurar pelo grupo {group_number} e posição {position} (ex: (7) A1)
   - Procurar pelo nome "{name}"
   - Confirmar que é a pessoa correta

2. **EXTRAIR DIAS DE TRABALHO NORMAL (CRÍTICO - NÃO INVENTAR DATAS):**
   
   **ESTRUTURA DO DOCUMENTO:**
   O documento tem esta estrutura EXATA:
   - Cada semana tem uma seção "SEMANA X"
   - Abaixo de "SEMANA X" há uma linha com cabeçalhos: "Setor:", "Local:", "Turno:", "Preceptor Responsável", seguido das datas DD/MM nas colunas dos dias
   - Exemplo linha de datas: "Setor: | Local: | Turno: | Preceptor Responsável | 27/10 | 28/10 | 29/10 | 30/10 | 31/10 | 01/11 | 02/11"
   - As colunas após "Preceptor Responsável" correspondem a: SEG | TER | QUA | QUI | SEX | SÁB | DOM
   - Nas linhas seguintes, cada linha representa um turno, e nas colunas dos dias aparecem NÚMEROS que representam os GRUPOS
   - Exemplo: Se na linha "Global | UPA2 | 07:00 - 13:00 | Mattheus | 1 | 1 | 1 | 1 | 1 | * | *"
     Isso significa que o GRUPO 1 trabalha nesse turno nos dias Seg, Ter, Qua, Qui, Sex (colunas com "1")
   
   **REGRA FUNDAMENTAL:** Extrair APENAS os dias onde o número {group_number} aparece EXATAMENTE na tabela de cada semana!
   
   **PROCESSO OBRIGATÓRIO PARA DIAS DE TRABALHO:**
   
   1. **PARA CADA SEMANA (Semana 1, Semana 2, etc.):**
      - Localizar a seção "SEMANA X"
      - Encontrar a linha com as DATAS (ex: "27/10 | 28/10 | 29/10 | 30/10 | 31/10 | 01/11 | 02/11")
      - Identificar qual coluna corresponde a qual dia da semana:
        * Primeira coluna de data = SEG
        * Segunda coluna de data = TER
        * Terceira coluna de data = QUA
        * Quarta coluna de data = QUI
        * Quinta coluna de data = SEX
        * Sexta coluna de data = SÁB
        * Sétima coluna de data = DOM
   
   2. **PROCURAR O NÚMERO {group_number} NAS LINHAS DE TURNO:**
      - Para cada linha de turno (após a linha de datas), verificar se o número {group_number} aparece
      - O número pode aparecer sozinho (ex: "7") ou com outros (ex: "7 + 8" ou "1 + 7")
      - Se o número {group_number} aparece na coluna de uma data específica, então esse é um dia de trabalho
      - Exemplo: Se grupo=7 e na linha "Global | UPA2 | 13:00 - 19:00 | Ely | 2 + 8 | 2 + 8 | 2 + 8 | 2 + 8 | 2 + 8 | - | -"
        E a linha de datas é "27/10 | 28/10 | 29/10 | 30/10 | 31/10 | 01/11 | 02/11"
        Então o grupo 7 NÃO trabalha nesse turno (porque aparece "2 + 8", não "7")
   
   3. **QUANDO ENCONTRAR O NÚMERO {group_number}:**
      - Identificar a COLUNA onde o número aparece (qual dia da semana)
      - Pegar a DATA DD/MM da mesma coluna na linha de datas
      - Extrair informações da LINHA:
        * Setor: primeira coluna da linha
        * Local: segunda coluna da linha
        * Turno/Horário: terceira coluna da linha
        * Preceptor: quarta coluna da linha
      - Criar um evento de trabalho com essas informações
   
   4. **CRÍTICO - NÃO INVENTAR:**
      - EXTRAIR APENAS os dias onde o número {group_number} REALMENTE aparece no documento
      - NÃO criar dias de trabalho que não estão no documento
      - NÃO assumir que todos os dias da semana têm trabalho
      - Se o número {group_number} aparece apenas em Seg, Ter, Qua, Qui, Sex, então EXTRAIR APENAS esses dias
      - Se não aparece em Sábado e Domingo, NÃO criar eventos para esses dias!
      - Se aparece "*" ou "-" na coluna, significa que NÃO há trabalho nesse dia
      - Se aparece outro número (ex: "1", "2", "3") mas não {group_number}, então NÃO há trabalho nesse dia
   
   5. **ORGANIZAR POR SEMANA:**
      - Identificar qual semana (Semana 1, Semana 2, etc.)
      - Extrair datas APENAS no formato DD/MM (ex: 03/11, 04/11) - NÃO converter para YYYY-MM-DD!
      - NÃO tentar adivinhar o ano - extrair apenas dia e mês!
      - Organizar por semana e dia da semana

3. **EXTRAIR PLANTÕES (CRÍTICO - PRECISÃO ABSOLUTA):**
   
   **REGRA FUNDAMENTAL:** O dia da semana do plantão é determinado pela COLUNA onde ele aparece no PDF, NÃO pelo dia que vem antes dele no texto!
   
   **PROCESSO OBRIGATÓRIO PARA PLANTÕES:**
   
   1. **PROCURAR NA TABELA "PLANTÃO":**
      - Procurar APENAS na tabela "PLANTÃO" (não na tabela "MAPA RECEPTOR")
      - Procurar APENAS onde aparece ({group_number}) {position} ou ({group_number}){position}
      - Exemplo: Se grupo=7 e posição=A1, procurar por "(7) A1" ou "(7)A1"
   
   2. **IDENTIFICAR A COLUNA (CRÍTICO):**
      - O documento está estruturado como PLANILHA com colunas para cada dia
      - Verificar em qual COLUNA o código ({group_number}) {position} aparece:
        - Se está na coluna "SEGUNDA" ou "Segunda" ou "Seg", day_of_week = "Seg"
        - Se está na coluna "TERÇA" ou "Terça" ou "Ter", day_of_week = "Ter"
        - Se está na coluna "QUARTA" ou "Quarta" ou "Qua", day_of_week = "Qua"
        - Se está na coluna "QUINTA" ou "Quinta" ou "Qui", day_of_week = "Qui"
        - Se está na coluna "SEXTA" ou "Sexta" ou "Sex", day_of_week = "Sex"
        - Se está na coluna "SÁBADO" ou "Sábado" ou "Sáb", day_of_week = "Sáb"
        - Se está na coluna "DOMINGO" ou "Domingo" ou "Dom", day_of_week = "Dom"
   
   3. **IDENTIFICAR A DATA:**
      - Procurar pela data DD/MM na linha de datas da semana correspondente
      - A data está na mesma coluna do plantão
      - Exemplo: Se o plantão está na coluna "DOMINGO" da Semana 2, procurar a data na linha de datas da Semana 2, coluna "DOMINGO"
      - EXTRAIR APENAS DD/MM - NÃO tentar adivinhar o ano!
   
   4. **EXTRAIR INFORMAÇÕES DO PLANTÃO:**
      - Local: Na mesma linha do plantão, coluna "LOCAL" ou primeira coluna
      - Tipo: "Plantão Cinderela", "Plantão Diurno", "Plantão Noturno", etc.
      - Horário: Na mesma linha, coluna "HORÁRIO"
   
   **ATENÇÃO CRÍTICA - NÃO ERRAR O DIA:**
   - O plantão está na TABELA "PLANTÃO", não na "MAPA RECEPTOR"
   - O day_of_week é determinado pela COLUNA onde o código aparece, NÃO pelo texto ao redor!
   - Exemplo: Se o texto mostra "Terça | Trabalho | ... | (7) A1", mas (7) A1 está na COLUNA "DOMINGO" da tabela PLANTÃO, então day_of_week = "Dom"!
   - NUNCA assuma que o plantão é do mesmo dia que aparece antes dele no texto!
   - SEMPRE verifique a estrutura de colunas da planilha!
   - Se o documento está estruturado como "Linha X: Col1 | Col2 | ... | ColDom", e (7) A1 está em ColDom, então é Domingo!
   
   - Extrair local, tipo de plantão, horários
   - Confirmar que é realmente um plantão

4. **VALIDAÇÃO DE DATAS E DIAS (OBRIGATÓRIO - CRÍTICO PARA PRECISÃO):**
   - VERIFICAR A ESTRUTURA DE COLUNAS: O PDF está estruturado como planilha com colunas
   - Cada coluna representa um dia da semana (Seg, Ter, Qua, Qui, Sex, Sáb, Dom)
   - O plantão pertence à COLUNA onde aparece, não ao texto ao redor
   - Exemplo: Se o plantão está na coluna "Dom" com data "03/11", então:
     - date: "03/11"
     - day_of_week: "Dom" (da coluna, não do texto!)
   - NÃO confundir: Se o plantão está na coluna "Dom", NÃO pode ser "Ter" ou qualquer outro dia!
   - VALIDAR: A data DD/MM deve estar na mesma linha/coluna do plantão
   - NÃO tentar adivinhar o ano - apenas extrair DD/MM!
   - **VALIDAÇÃO CRÍTICA:** Após extrair a data DD/MM e o day_of_week, VERIFIQUE se a data corresponde ao dia da semana correto!
   - Exemplo: Se extraiu "02/11" como "Seg", verifique: 02/11/2025 é realmente Segunda? Se não for, CORRIJA o day_of_week ou a data!
   - Use a data atual ({current_date_str}) como referência para validar se as datas fazem sentido

5. **EXTRAIR PRECEPTOR RESPONSÁVEL:**
   - Identificar o preceptor responsável de cada semana
   - Cada semana pode ter um preceptor diferente
   - Procurar por informações como "Preceptor", "Responsável", nomes de médicos/preceptores
   - Associar o preceptor à semana correspondente

6. **RETORNAR JSON ESTRUTURADO:**

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
      "date": "DD/MM",
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
      "date": "DD/MM",
      "day_of_week": "Dom",
      "week": 2,
      "location": "UPA1",
      "shift_type": "Plantão Cinderela",
      "start_time": "HH:MM",
      "end_time": "HH:MM",
      "preceptor": "Nome do Preceptor"
    }}
  ]
}}

**REGRAS CRÍTICAS DE PRECISÃO - CONFIE NO DOCUMENTO:**
- PRECISÃO ABSOLUTA: Extraia EXATAMENTE como está no documento - SEM VALIDAÇÃO EXTERNA!
- FONTE DA VERDADE: O documento JÁ tem as datas e dias da semana corretos nas colunas
- NÃO VALIDE: NÃO tente verificar se a data corresponde ao dia da semana usando calendários!
- NÃO CORRIJA: NÃO tente "corrigir" baseado em conhecimento de calendário!
- EXTRAÇÃO DIRETA: Se "27/10" está na coluna "SEG", então:
  * date: "27/10"
  * day_of_week: "Seg"
  * FIM - não precisa verificar mais nada!
- DIAS DA SEMANA: Seg, Ter, Qua, Qui, Sex, Sáb, Dom - use exatamente como aparece na coluna!
- PLANTÕES: Se está na coluna "Dom", day_of_week DEVE ser "Dom" - SEM EXCEÇÃO!
- DATAS: Extrair APENAS no formato DD/MM (ex: "03/11", "04/11") - NÃO incluir o ano!
- ANO: Todas as datas são de {current_year} (2025) - mas NÃO valide isso, apenas use como referência
- SEM ERROS: Um erro pode fazer o médico perder um plantão ou ir no dia errado!
- APENAS JSON: Retorne APENAS o JSON, sem texto adicional
- HORÁRIOS: Use formato HH:MM (24h)

**EXEMPLO DE EXTRAÇÃO CORRETA DE PLANTÃO:**
- Se o PDF mostra (estrutura de planilha):
  ```
  Coluna Seg | Coluna Ter | Coluna Qua | ... | Coluna Dom
  Trabalho   | Trabalho   | Trabalho   | ... | (7) A1 Plantão
  27/10      | 28/10      | 29/10      | ... | 03/11
  ```
- Então o plantão:
  - date: "03/11" (apenas DD/MM, sem ano!)
  - day_of_week: "Dom" (da COLUNA onde está, não do texto!)
  - week: calcular baseado na semana do calendário
  
**ERRO COMUM A EVITAR:**
- NÃO fazer: Se o texto mostra "Terça | ... | Plantão", assumir que day_of_week = "Ter"
- FAZER: Verificar em qual COLUNA o plantão está e usar o dia da semana dessa coluna!

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
                    timeout=150.0  # 150 segundos (2.5 minutos) máximo para Gemini processar
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

