"""Ferramentas compartilhadas pelos testes: configuração isolada e um Ollama falso."""

import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, Optional
from unittest import mock

from rpgassistant import config


def resposta(texto: str, prompt_tokens: int = 100, completion_tokens: int = 20) -> Dict[str, Any]:
    """Resposta completa no formato do Ollama."""
    return {"message": {"content": texto}, "prompt_eval_count": prompt_tokens, "eval_count": completion_tokens}


def pedacos(textos: Iterable[str], final: tuple = (11, 5)) -> Iterator[Dict[str, Any]]:
    """Pedaços de uma resposta em streaming; o último traz as métricas, como no Ollama."""
    lista = list(textos)
    for i, texto in enumerate(lista):
        chunk: Dict[str, Any] = {"message": {"content": texto}}
        if i == len(lista) - 1:
            chunk.update(done=True, prompt_eval_count=final[0], eval_count=final[1])
        yield chunk


class RelogioFalso:
    """Relógio que avança um segundo a cada chamada, para os testes terem datas previsíveis e distintas."""

    def __init__(self) -> None:
        self._agora = datetime(2026, 10, 28, 12, 0, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        self._agora += timedelta(seconds=1)
        return self._agora


class OllamaFalso:
    """
    Substitui `rpgassistant.services.llm._ollama_chat`. Registra as chamadas em `chamadas` e responde
    com `texto`, com `chunks` (se pedido stream), com `responder(kwargs)` ou levanta `falha`.
    """

    def __init__(self, texto: str = "ok", chunks: Optional[Iterable[str]] = None,
                 falha: Optional[Exception] = None, responder: Optional[Callable[[dict], Any]] = None) -> None:
        self.texto = texto
        self.chunks = list(chunks) if chunks is not None else None
        self.falha = falha
        self.responder = responder
        self.chamadas: list = []

    def __call__(self, **kwargs: Any) -> Any:
        self.chamadas.append(kwargs)
        if self.falha:
            raise self.falha
        if self.responder:
            return self.responder(kwargs)
        if kwargs.get("stream"):
            return pedacos(self.chunks if self.chunks is not None else [self.texto])
        return resposta(self.texto)


class BaseTeste(unittest.TestCase):
    """Instala uma configuração isolada (pasta temporária) em `config.settings` durante cada teste."""

    def setUp(self) -> None:
        super().setUp()
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.pasta = Path(pasta.name)
        self.cfg = replace(config.Config(), data_dir=self.pasta)
        padrao = mock.patch.object(config, "settings", self.cfg)
        padrao.start()
        self.addCleanup(padrao.stop)

    def usar_ollama(self, falso: OllamaFalso) -> OllamaFalso:
        padrao = mock.patch("rpgassistant.services.llm._ollama_chat", falso)
        padrao.start()
        self.addCleanup(padrao.stop)
        return falso

    def usar_busca(self, contexto: str = "CTX", fontes: str = "Core | PHB", similaridade: Optional[float] = 0.9) -> "BuscaFalsa":
        """Substitui a busca nos livros. Devolve um objeto-lista com as consultas recebidas (query, k)."""
        busca = BuscaFalsa(contexto, fontes, similaridade)
        for nome in ("recuperar_contexto", "buscar_contexto"):
            padrao = mock.patch(f"rpgassistant.services.rag.{nome}", getattr(busca, nome))
            padrao.start()
            self.addCleanup(padrao.stop)
        return busca


class BuscaFalsa(list):
    """Lista de (consulta, k). Mude `similaridade` ou `base_vazia` no meio do teste para simular situações."""

    def __init__(self, contexto: str, fontes: str, similaridade: Optional[float]) -> None:
        super().__init__()
        self.contexto, self.fontes, self.similaridade, self.base_vazia = contexto, fontes, similaridade, False

    def buscar_contexto(self, query: str, k: Optional[int] = None):
        from rpgassistant.errors import BaseVaziaError
        from rpgassistant.services.rag import ResultadoBusca
        self.append((query, k))
        if self.base_vazia:
            raise BaseVaziaError("A base de livros ainda não foi indexada. Rode: python -m rpgassistant.indexar")
        return ResultadoBusca(self.contexto, self.fontes, self.similaridade, 1)

    def recuperar_contexto(self, query: str, k: Optional[int] = None):
        self.append((query, k))
        return self.contexto, self.fontes


# ---------- respostas de exemplo e um "modelo" que escolhe a resposta pelo prompt ----------
VALIDA = '[Ação]: Lia olha ao redor.\n[Fala]: "O que vemos, Mestre?"'
FEEDBACK = "**Pontos Fortes** boa imersão.\n**Aplicação de Regras e Testes** bons testes.\n**Dica de Mestre** dê ganchos."
COMBATE = "O goblin ataca! Acerta 4 de dano. O que você faz?\n[ESTADO] Jogador PV 11/15 | Goblin PV 7/7 CA 15"
CENA = "Você vê um corredor escuro. O que você faz?"
AGARRADO = "Agarrado [Grappled] reduz a velocidade a 0. (Core | PHB)"


def modelo(kwargs):
    """Ollama falso: escolhe a resposta pelo prompt do sistema, como o modelo de verdade faria."""
    mensagens = kwargs["messages"]
    sistema = mensagens[0]["content"] if mensagens[0]["role"] == "system" else ""
    ultimo = mensagens[-1]["content"]
    if mensagens[0]["role"] == "user" and ultimo.startswith("Reescreva"):
        return resposta("Como funciona a condição Agarrado para um personagem cego?")
    if "Mentor de RPG" in sistema:
        texto = FEEDBACK
    elif "Dungeon Master" in sistema:
        texto = COMBATE if "Ataco" in ultimo else CENA
    elif "jogador de RPG" in sistema:
        texto = VALIDA
    else:
        texto = AGARRADO
    if kwargs.get("stream"):
        palavras = texto.split(" ")
        return pedacos([p + " " for p in palavras[:-1]] + [palavras[-1]], final=(321, 45))
    return resposta(texto)