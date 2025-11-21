"""Graph Workflow para orquestração de agentes."""

from typing import Any, Dict, Literal, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.calendar_organizer import CalendarOrganizerAgent
from app.agents.medical_assistant import MedicalAssistantAgent
from app.agents.note_analyzer import NoteAnalyzerAgent


class AgentState(TypedDict):
    """Estado compartilhado entre agentes."""

    # Comum
    messages: list[Dict[str, str]]
    agent_used: str
    error: str | None

    # Medical Assistant
    question: str | None
    answer: str | None
    context_used: list | None
    has_context: bool | None

    # Note Analyzer
    note_id: str | None
    note_title: str | None
    analysis: str | None

    # Calendar Organizer
    calendar_text: str | None
    organized_calendar: str | None

    # Database
    user_id: str | None
    db: Any | None


class AgentOrchestrator:
    """Orquestrador de agentes usando LangGraph."""

    def __init__(self):
        """Inicializa o orquestrador de agentes."""
        self.medical_assistant = MedicalAssistantAgent()
        self.note_analyzer = NoteAnalyzerAgent()
        self.calendar_organizer = CalendarOrganizerAgent()

        # Criar grafo
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """
        Constrói o grafo de agentes.

        Returns:
            StateGraph: Grafo configurado.
        """
        workflow = StateGraph(AgentState)

        # Adicionar nós
        workflow.add_node("medical_assistant", self._medical_assistant_node)
        workflow.add_node("note_analyzer", self._note_analyzer_node)
        workflow.add_node("calendar_organizer", self._calendar_organizer_node)

        # Definir ponto de entrada
        workflow.set_entry_point("router")
        workflow.add_node("router", self._router_node)

        # Adicionar arestas
        workflow.add_conditional_edges(
            "router",
            self._route_to_agent,
            {
                "medical_assistant": "medical_assistant",
                "note_analyzer": "note_analyzer",
                "calendar_organizer": "calendar_organizer",
                "end": END,
            },
        )

        # Todos os agentes vão para o fim
        workflow.add_edge("medical_assistant", END)
        workflow.add_edge("note_analyzer", END)
        workflow.add_edge("calendar_organizer", END)

        return workflow.compile()

    def _router_node(self, state: AgentState) -> AgentState:
        """
        Nó roteador que decide qual agente usar.

        Args:
            state: Estado atual.

        Returns:
            AgentState: Estado atualizado.
        """
        # O roteamento é feito pela função de roteamento
        return state

    def _route_to_agent(
        self, state: AgentState
    ) -> Literal["medical_assistant", "note_analyzer", "calendar_organizer", "end"]:
        """
        Decide qual agente usar baseado no estado.

        Args:
            state: Estado atual.

        Returns:
            str: Nome do próximo nó.
        """
        # Determinar agente baseado nos campos presentes
        if state.get("question"):
            return "medical_assistant"
        elif state.get("note_id"):
            return "note_analyzer"
        elif state.get("calendar_text"):
            return "calendar_organizer"
        else:
            return "end"

    async def _medical_assistant_node(self, state: AgentState) -> AgentState:
        """
        Nó do Medical Assistant.

        Args:
            state: Estado atual.

        Returns:
            AgentState: Estado atualizado.
        """
        result = await self.medical_assistant.execute(state)
        return result

    async def _note_analyzer_node(self, state: AgentState) -> AgentState:
        """
        Nó do Note Analyzer.

        Args:
            state: Estado atual.

        Returns:
            AgentState: Estado atualizado.
        """
        result = await self.note_analyzer.execute(state)
        return result

    async def _calendar_organizer_node(self, state: AgentState) -> AgentState:
        """
        Nó do Calendar Organizer.

        Args:
            state: Estado atual.

        Returns:
            AgentState: Estado atualizado.
        """
        result = await self.calendar_organizer.execute(state)
        return result

    async def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa o grafo de agentes.

        Args:
            initial_state: Estado inicial.

        Returns:
            Dict[str, Any]: Estado final.
        """
        # Converter para AgentState
        state: AgentState = {
            "messages": initial_state.get("messages", []),
            "agent_used": None,
            "error": None,
            "question": initial_state.get("question"),
            "answer": None,
            "context_used": None,
            "has_context": None,
            "note_id": initial_state.get("note_id"),
            "note_title": None,
            "analysis": None,
            "calendar_text": initial_state.get("calendar_text"),
            "organized_calendar": None,
            "user_id": initial_state.get("user_id"),
            "db": initial_state.get("db"),
        }

        # Executar grafo
        result = await self.graph.ainvoke(state)

        return result

