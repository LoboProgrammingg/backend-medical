"""Note Analyzer Agent - Analisa e melhora anotações."""

from typing import Any, Dict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base_agent import BaseAgent
from app.models.note import Note


class NoteAnalyzerAgent(BaseAgent):
    """Agente que analisa e fornece insights sobre anotações."""

    SYSTEM_PROMPT = """Você é um especialista em análise de conteúdo médico-acadêmico.

**SUA FUNÇÃO:**
Analisar anotações de estudantes de medicina e fornecer:
1. Avaliação de completude do conteúdo
2. Sugestões de complementação
3. Identificação de gaps de conhecimento
4. Recomendações de organização
5. Sugestões de tags relevantes

**CRITÉRIOS DE ANÁLISE:**
- **Completude:** O conteúdo cobre os aspectos essenciais do tema?
- **Clareza:** As informações estão bem estruturadas?
- **Profundidade:** Há detalhes clínicos suficientes?
- **Relevância:** O conteúdo está focado no tema principal?

**FORMATO DE RESPOSTA:**

📊 **ANÁLISE DA ANOTAÇÃO: [Título]**

✅ **Pontos Fortes:**
• [Aspecto 1]
• [Aspecto 2]

⚠️ **Pontos de Melhoria:**
• [Sugestão 1]
• [Sugestão 2]

📚 **Sugestões de Complementação:**
• [Tópico para adicionar 1]
• [Tópico para adicionar 2]

🏷️ **Tags Sugeridas:**
• [Tag 1] • [Tag 2] • [Tag 3]

💡 **Próximos Passos:**
[Orientação sobre como melhorar ou expandir]

**DIRETRIZES:**
- Seja construtiva e encorajadora
- Foque em melhorias práticas
- Considere o contexto acadêmico médico
- Sugira conexões com outros tópicos
- Use emojis para clareza visual"""

    def __init__(self):
        """Inicializa o Note Analyzer Agent."""
        super().__init__(
            name="Note Analyzer",
            system_prompt=self.SYSTEM_PROMPT,
        )

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa análise de anotação.

        Args:
            state: Estado atual contendo:
                - note_id: ID da anotação
                - user_id: ID do usuário
                - db: Sessão do banco

        Returns:
            Dict[str, Any]: Estado atualizado com análise.
        """
        note_id = state["note_id"]
        user_id = state["user_id"]
        db: AsyncSession = state["db"]

        # Buscar anotação
        result = await db.execute(
            select(Note).where(Note.id == note_id, Note.user_id == user_id)
        )
        note = result.scalar_one_or_none()

        if not note:
            state["error"] = "Anotação não encontrada"
            return state

        # Análise da anotação
        analysis_prompt = f"""Analise a seguinte anotação médica:

**TÍTULO:** {note.title}

**CONTEÚDO:**
{note.content}

**TAGS ATUAIS:** {', '.join(note.tags) if note.tags else 'Nenhuma'}

**TAREFAS:**
1. Avalie a completude e qualidade do conteúdo
2. Identifique gaps de informação
3. Sugira complementações
4. Recomende tags adicionais
5. Forneça orientações para melhoria"""

        analysis = await self.generate_response(analysis_prompt)

        state["analysis"] = analysis
        state["note_title"] = note.title
        state["agent_used"] = self.name

        return state

    async def analyze_multiple_notes(
        self,
        user_id: UUID,
        db: AsyncSession,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Analisa múltiplas anotações e identifica padrões.

        Args:
            user_id: ID do usuário.
            db: Sessão do banco.
            limit: Número de notas a analisar.

        Returns:
            Dict[str, Any]: Análise geral.
        """
        # Buscar anotações recentes
        result = await db.execute(
            select(Note)
            .where(Note.user_id == user_id)
            .order_by(Note.updated_at.desc())
            .limit(limit)
        )
        notes = result.scalars().all()

        if not notes:
            return {
                "summary": "Nenhuma anotação encontrada para análise.",
                "recommendations": [],
            }

        # Preparar dados para análise
        notes_summary = "\n\n".join(
            [
                f"**{i+1}. {note.title}**\n"
                f"Tags: {', '.join(note.tags) if note.tags else 'Nenhuma'}\n"
                f"Tamanho: {len(note.content)} caracteres"
                for i, note in enumerate(notes)
            ]
        )

        analysis_prompt = f"""Analise o conjunto de {len(notes)} anotações mais recentes deste estudante de medicina:

{notes_summary}

**FORNEÇA:**
1. 📊 **Visão Geral:** Padrão de estudo identificado
2. 🎯 **Áreas de Foco:** Especialidades mais estudadas
3. ⚠️ **Gaps Identificados:** Áreas que precisam de atenção
4. 💡 **Recomendações:** Sugestões de estudo
5. 🏷️ **Organização:** Sugestões de melhor categorização

Seja objetiva e forneça insights práticos."""

        analysis = await self.generate_response(analysis_prompt)

        return {
            "summary": analysis,
            "total_notes_analyzed": len(notes),
            "agent": self.name,
        }

    async def suggest_improvements(
        self,
        note_content: str,
        note_title: str,
    ) -> Dict[str, Any]:
        """
        Sugere melhorias para uma anotação.

        Args:
            note_content: Conteúdo da anotação.
            note_title: Título da anotação.

        Returns:
            Dict[str, Any]: Sugestões de melhoria.
        """
        prompt = f"""Como especialista, sugira melhorias específicas para esta anotação:

**TÍTULO:** {note_title}
**CONTEÚDO:**
{note_content}

**FORNEÇA:**
1. ✍️ **Reescrita Sugerida** (se necessário)
2. 📝 **Tópicos a Adicionar**
3. 🔍 **Detalhamento Necessário**
4. 🎯 **Foco Principal** (o que manter/remover)

Seja específica e prática."""

        suggestions = await self.generate_response(prompt)

        return {
            "suggestions": suggestions,
            "original_title": note_title,
            "agent": self.name,
        }

