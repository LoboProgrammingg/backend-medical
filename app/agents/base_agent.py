"""Base Agent para todos os agentes do sistema."""

from abc import ABC, abstractmethod
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config.settings import settings


class BaseAgent(ABC):
    """Classe base para todos os agentes."""

    def __init__(self, name: str, system_prompt: str):
        """
        Inicializa o agente base.

        Args:
            name: Nome do agente.
            system_prompt: Prompt do sistema para o agente.
        """
        self.name = name
        self.system_prompt = system_prompt
        self.llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.google_api_key,
            temperature=0.7,
            max_output_tokens=settings.max_output_tokens,
            top_k=settings.top_k,
        )

    @abstractmethod
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa a lógica do agente.

        Args:
            state: Estado atual do grafo.

        Returns:
            Dict[str, Any]: Estado atualizado.
        """
        pass

    async def generate_response(self, user_message: str) -> str:
        """
        Gera uma resposta usando o LLM (com retry para rate limiting).

        Args:
            user_message: Mensagem do usuário.

        Returns:
            str: Resposta gerada.
        """
        import asyncio
        from google.api_core import exceptions as google_exceptions
        
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_message),
        ]

        # Tentar com retry exponencial
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self.llm.ainvoke(messages)
                return response.content
            except google_exceptions.ResourceExhausted as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 2  # 2s, 4s, 8s
                    print(f"⚠️ Rate limit atingido. Aguardando {wait_time}s antes de tentar novamente...")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"❌ Rate limit excedido após {max_retries} tentativas")
                    return "Desculpe, estou temporariamente sobrecarregada devido ao alto volume de requisições. Por favor, aguarde alguns segundos e tente novamente. 😔"
            except Exception as e:
                print(f"❌ Erro ao gerar resposta: {type(e).__name__}: {e}")
                return f"Desculpe, ocorreu um erro ao processar sua mensagem. Tente novamente em alguns instantes."

    def __repr__(self) -> str:
        """Representação string do agente."""
        return f"<{self.__class__.__name__}(name={self.name})>"

