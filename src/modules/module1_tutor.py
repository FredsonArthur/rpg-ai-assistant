"""
Módulo 1: Tutor de Regras, Lore e Geração de Conteúdo (UC01, UC02, UC03)
------------------------------------------------------------------------
Responsável por gerir as interações do utilizador com o motor RAG unificado,
consultando os manuais core e suplementos de D&D 5e.
"""

from src.rag_engine import query_rag
from src.prompt_templates import SYSTEM_PROMPT

def run_module1_chat(user_input: str):
    """
    Executa a consulta ao Módulo 1 e retorna a resposta da LLM,
    as fontes consultadas e as métricas de tokens.
    """
    response_text, sources, metrics = query_rag(
        user_input, 
        prompt_template=SYSTEM_PROMPT
    )
    return response_text, sources, metrics