"""
Histórico enviado ao modelo
---------------------------
Os tipos do histórico (uma lista de mensagens com "role" e "content") e a função que escolhe quais
mensagens recentes vão ao modelo em cada turno.
"""

from typing import Dict, List

Mensagem = Dict[str, str]
Historico = List[Mensagem]


def janela_historico(chat_history: Historico, tamanho: int) -> Historico:
    """
    Seleciona as mensagens que vão ao modelo: no máximo `tamanho`, sempre preservando a
    primeira (a abertura da cena) e as mais recentes. Assim, uma conversa longa não perde
    o ponto de partida da aventura. O recorte mantém a alternância usuário/assistente.

    Pressupõe que a conversa ABRE com uma fala do assistente (a abertura da cena do Mestre ou a saudação
    do Jogador). Em uma conversa que abre com o usuário, como a do modo Assistente, o recorte deixaria duas
    falas do usuário seguidas; por isso o Assistente não usa esta função (veja modes/assistente.py).
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