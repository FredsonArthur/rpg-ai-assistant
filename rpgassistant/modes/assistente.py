"""
Modo Assistente (UC01, UC02, UC03)
----------------------------------
Responde dúvidas de regras e lore, e cria conteúdo (NPCs, encontros, itens), apenas com o que está nos
livros da base vetorial (veja core/policy.py), com memória da conversa.

Fluxo: `preparar` reescreve a pergunta com o histórico, busca nos livros e aplica a barreira de
relevância; `iniciar_stream` chama o modelo para as perguntas que passaram.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from rpgassistant import config
from rpgassistant.core import policy
from rpgassistant.core.historico import Historico, Mensagem
from rpgassistant.services import llm, rag
from rpgassistant.services.prompts import LIVROS_PROMPT


@dataclass(frozen=True)
class Consulta:
    """Uma pergunta já pesquisada nos livros, pronta para o modelo (ou já recusada, sem chamá-lo)."""

    pergunta: str
    consulta_busca: str                  # a pergunta reescrita usada na busca
    fontes: str
    melhor_similaridade: Optional[float]
    mensagens: List[Mensagem]            # vazio quando a pergunta foi recusada
    recusada: bool
    motivo_recusa: str = ""


def formatar_metricas(prompt_tokens: int, completion_tokens: int, consulta: str, pergunta: str) -> str:
    """Texto de métricas exibido ao usuário (tokens usados e, se houve, a busca reescrita)."""
    metricas = f"Prompt Tokens: {prompt_tokens} | Completion Tokens: {completion_tokens}"
    if consulta != pergunta:
        metricas += f" | Busca reescrita: {consulta}"
    return metricas


def preparar(pergunta: str, historico: Optional[Historico] = None,
             prompt_template: str = LIVROS_PROMPT) -> Consulta:
    """
    Reescreve a pergunta com o histórico, busca nos livros e aplica a barreira de relevância.
    Levanta BaseVaziaError se os livros ainda não foram indexados. Não chama o modelo para responder.
    """
    historico = historico or []
    consulta_busca = rag.reescrever_pergunta(pergunta, historico)
    resultado = rag.buscar_contexto(consulta_busca, k=config.settings.top_k_assistente)

    minimo = config.settings.relevancia_minima
    if not policy.avaliar_relevancia(resultado.melhor_similaridade, minimo):
        return Consulta(pergunta, consulta_busca, "", resultado.melhor_similaridade, [], True,
                        policy.motivo_da_recusa(resultado.melhor_similaridade, minimo))

    mensagens: List[Mensagem] = [{"role": "system", "content": prompt_template.format(context=resultado.contexto)}]
    for msg in historico[-config.settings.history_window:]:
        mensagens.append({"role": msg["role"], "content": msg["content"]})
    mensagens.append({"role": "user", "content": pergunta})
    return Consulta(pergunta, consulta_busca, resultado.fontes, resultado.melhor_similaridade, mensagens, False)


def iniciar_stream(consulta: Consulta) -> llm.RespostaEmStream:
    """Chama o modelo, em streaming, para uma consulta que não foi recusada."""
    return llm.chat_llm_stream(consulta.mensagens, temperature=config.settings.temperatura_assistente)