"""
Funções utilitárias compartilhadas entre os módulos.
"""

from typing import List


def janela_historico(chat_history: List[dict], tamanho: int) -> List[dict]:
    """
    Seleciona as mensagens que vão ao modelo: no máximo `tamanho`, sempre preservando a
    primeira (a abertura da cena) e as mais recentes. Assim, uma conversa longa não perde
    o ponto de partida da aventura. O recorte mantém a alternância usuário/assistente.
    """
    if tamanho <= 0:
        return []
    if len(chat_history) <= tamanho:
        return list(chat_history)
    if tamanho == 1:
        return [chat_history[-1]]

    recentes = chat_history[-(tamanho - 1):]
    if recentes[0]["role"] == "assistant":  # evita duas falas seguidas do assistente
        recentes = recentes[1:]
    return [chat_history[0]] + recentes