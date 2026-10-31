"""
Modo Assistente (UC01, UC02, UC03)
----------------------------------
Responde dúvidas de regras e lore, e cria conteúdo (NPCs, encontros, itens), com apoio dos livros
da base vetorial e memória da conversa.

O fluxo atual é `preparar` + `iniciar_stream`: ele só responde com o que está nos livros (veja
core/policy.py). As funções `responder` e `responder_stream`, mais abaixo, são do app antigo em
Streamlit, que também respondia perguntas gerais, e saem junto com ele.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from rpgassistant import config
from rpgassistant.core import policy
from rpgassistant.core.historico import Historico, Mensagem
from rpgassistant.services import llm, rag
from rpgassistant.services.prompts import LIVROS_PROMPT, SYSTEM_PROMPT


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


def formatar_metricas(prompt_tokens: int, completion_tokens: int, consulta: str, pergunta: str) -> str:
    """Texto de métricas exibido ao usuário (tokens usados e, se houve, a busca reescrita)."""
    metricas = f"Prompt Tokens: {prompt_tokens} | Completion Tokens: {completion_tokens}"
    if consulta != pergunta:
        metricas += f" | Busca reescrita: {consulta}"
    return metricas


def _preparar_consulta(pergunta: str, historico: Optional[Historico],
                       prompt_template: str) -> Tuple[list, str, str]:
    """
    Passos comuns da consulta: reescreve a pergunta (usando o histórico), busca os trechos nos livros
    e monta as mensagens (prompt do sistema + histórico recente + pergunta).
    Retorna (mensagens, fontes, consulta usada na busca).
    """
    historico = historico or []

    consulta = rag.reescrever_pergunta(pergunta, historico)
    contexto, fontes = rag.recuperar_contexto(consulta, k=config.settings.top_k_assistente)

    system_prompt = prompt_template.format(context=contexto, question=pergunta)
    mensagens: list[Mensagem] = [{"role": "system", "content": system_prompt}]
    for msg in historico[-config.settings.history_window:]:
        mensagens.append({"role": msg["role"], "content": msg["content"]})
    mensagens.append({"role": "user", "content": pergunta})
    return mensagens, fontes, consulta


def responder(pergunta: str, historico: Optional[Historico] = None,
              prompt_template: str = SYSTEM_PROMPT) -> Tuple[str, str, str]:
    """
    Responde de uma vez só. `historico`: mensagens anteriores, SEM a pergunta atual.
    Retorna (resposta, fontes, métricas). Levanta OllamaError se o Ollama falhar.
    """
    mensagens, fontes, consulta = _preparar_consulta(pergunta, historico, prompt_template)
    response = llm.chat_llm(mensagens, temperature=config.settings.temperatura_assistente)

    metricas = formatar_metricas(
        response.get('prompt_eval_count', 0), response.get('eval_count', 0), consulta, pergunta
    )
    return response['message']['content'], fontes, metricas


def responder_stream(pergunta: str, historico: Optional[Historico] = None,
                     prompt_template: str = SYSTEM_PROMPT) -> Tuple[llm.RespostaEmStream, str, str]:
    """
    Como o `responder`, mas a resposta chega em streaming.
    Retorna (stream, fontes, consulta usada na busca); as métricas ficam no próprio stream depois
    que ele termina (use `formatar_metricas`).
    """
    mensagens, fontes, consulta = _preparar_consulta(pergunta, historico, prompt_template)
    stream = llm.chat_llm_stream(mensagens, temperature=config.settings.temperatura_assistente)
    return stream, fontes, consulta