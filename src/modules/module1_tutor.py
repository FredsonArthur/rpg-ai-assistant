"""
Módulo 1: Assistente de Regras, Lore e Geração de Conteúdo (UC01, UC02, UC03)
------------------------------------------------------------------------------
Responsável pelas interações do usuário com o motor RAG, consultando os manuais
core e suplementos de D&D 5e e mantendo a memória da conversa.
"""

from typing import Optional, Tuple

from src.rag_engine import query_rag, query_rag_stream, RespostaEmStream
from src.prompt_templates import SYSTEM_PROMPT


def run_module1_chat(user_input: str, chat_history: Optional[list] = None) -> Tuple[str, str, str]:
    """
    Executa a consulta ao assistente e retorna (resposta, fontes, métricas de tokens).

    chat_history: mensagens anteriores da conversa, SEM a mensagem atual (user_input).
    Levanta OllamaError se a LLM local estiver indisponível; quem chama decide como
    mostrar o erro, sem salvá-lo no histórico.
    """
    return query_rag(
        user_input,
        chat_history=chat_history,
        prompt_template=SYSTEM_PROMPT
    )


def run_module1_chat_stream(user_input: str, chat_history: Optional[list] = None
                            ) -> Tuple[RespostaEmStream, str, str]:
    """
    Como o run_module1_chat, mas a resposta chega em streaming.
    Retorna (stream, fontes, consulta usada na busca). Levanta OllamaError se o Ollama falhar.
    """
    return query_rag_stream(
        user_input,
        chat_history=chat_history,
        prompt_template=SYSTEM_PROMPT
    )