"""
Repositório de chats
--------------------
Lê e grava chats e mensagens no banco. Cada operação que mexe em mais de uma tabela roda dentro
de uma transação, então uma falha nunca deixa o banco pela metade.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from rpgassistant.core.models import (
    PAPEIS, TIPO_FALA, TIPOS, TITULO_PADRAO, Chat, MensagemChat, titulo_valido,
)
from rpgassistant.core.modos import MODOS
from rpgassistant.errors import ChatNaoEncontrado
from rpgassistant.storage.database import Database

logger = logging.getLogger(__name__)

Relogio = Callable[[], datetime]


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _json(valor: Optional[Dict[str, Any]]) -> str:
    return json.dumps(valor or {}, ensure_ascii=False)


def _dict(texto: str) -> Dict[str, Any]:
    """Lê um JSON salvo no banco. Se estiver ilegível, devolve vazio em vez de derrubar o app."""
    try:
        valor = json.loads(texto)
        return valor if isinstance(valor, dict) else {}
    except (TypeError, ValueError):
        logger.warning("JSON ilegível no banco de chats; usando valor vazio.")
        return {}


def _chat(linha: sqlite3.Row) -> Chat:
    return Chat(
        id=linha["id"], titulo=linha["titulo"], modo=linha["modo"], estado=_dict(linha["estado"]),
        criado_em=datetime.fromisoformat(linha["criado_em"]),
        atualizado_em=datetime.fromisoformat(linha["atualizado_em"]),
    )


def _mensagem(linha: sqlite3.Row) -> MensagemChat:
    return MensagemChat(
        id=linha["id"], chat_id=linha["chat_id"], ordem=linha["ordem"], papel=linha["papel"],
        conteudo=linha["conteudo"], tipo=linha["tipo"], extras=_dict(linha["extras"]),
        criado_em=datetime.fromisoformat(linha["criado_em"]),
    )


class RepositorioChats:
    """Acesso aos dados. `agora` pode ser trocado nos testes para controlar as datas."""

    def __init__(self, db: Database, agora: Relogio = _agora) -> None:
        self.db = db
        self._agora = agora

    # ---------- chats ----------
    def criar_chat(self, titulo: str = TITULO_PADRAO, modo: Optional[str] = None,
                   estado: Optional[Dict[str, Any]] = None) -> Chat:
        if modo is not None:
            self._validar_modo(modo)
        agora = self._agora().isoformat()
        with self.db.transaction():
            cursor = self.db.executar(
                "INSERT INTO chats (titulo, modo, estado, criado_em, atualizado_em) VALUES (?, ?, ?, ?, ?)",
                (titulo_valido(titulo), modo, _json(estado), agora, agora),
            )
        return self.obter_chat(cursor.lastrowid)

    def obter_chat(self, chat_id: int) -> Chat:
        linhas = self.db.consultar("SELECT * FROM chats WHERE id = ?", (chat_id,))
        if not linhas:
            raise ChatNaoEncontrado(f"O chat {chat_id} não existe.")
        return _chat(linhas[0])

    def listar_chats(self) -> List[Chat]:
        """Do mais recente (última atividade) para o mais antigo."""
        linhas = self.db.consultar("SELECT * FROM chats ORDER BY atualizado_em DESC, id DESC")
        return [_chat(linha) for linha in linhas]

    def renomear_chat(self, chat_id: int, titulo: str) -> Chat:
        self._atualizar("UPDATE chats SET titulo = ? WHERE id = ?", (titulo_valido(titulo), chat_id), chat_id)
        return self.obter_chat(chat_id)

    def definir_modo(self, chat_id: int, modo: str) -> Chat:
        self._validar_modo(modo)
        self._atualizar("UPDATE chats SET modo = ?, atualizado_em = ? WHERE id = ?",
                        (modo, self._agora().isoformat(), chat_id), chat_id)
        return self.obter_chat(chat_id)

    def salvar_estado(self, chat_id: int, estado: Dict[str, Any]) -> Chat:
        self._atualizar("UPDATE chats SET estado = ?, atualizado_em = ? WHERE id = ?",
                        (_json(estado), self._agora().isoformat(), chat_id), chat_id)
        return self.obter_chat(chat_id)

    def excluir_chat(self, chat_id: int) -> None:
        """Apaga o chat e, em cascata, todas as suas mensagens."""
        self._atualizar("DELETE FROM chats WHERE id = ?", (chat_id,), chat_id)

    # ---------- mensagens ----------
    def adicionar_mensagem(self, chat_id: int, papel: str, conteudo: str, tipo: str = TIPO_FALA,
                           extras: Optional[Dict[str, Any]] = None) -> MensagemChat:
        if papel not in PAPEIS:
            raise ValueError(f"Papel inválido: {papel!r} (use um de {', '.join(PAPEIS)}).")
        if tipo not in TIPOS:
            raise ValueError(f"Tipo inválido: {tipo!r} (use um de {', '.join(TIPOS)}).")
        agora = self._agora().isoformat()
        with self.db.transaction():
            self.obter_chat(chat_id)  # levanta ChatNaoEncontrado se não existir
            ordem = self.db.valor("SELECT COALESCE(MAX(ordem), 0) + 1 FROM mensagens WHERE chat_id = ?", (chat_id,))
            cursor = self.db.executar(
                "INSERT INTO mensagens (chat_id, ordem, papel, tipo, conteudo, extras, criado_em) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (chat_id, ordem, papel, tipo, conteudo, _json(extras), agora),
            )
            self.db.executar("UPDATE chats SET atualizado_em = ? WHERE id = ?", (agora, chat_id))
        return _mensagem(self.db.consultar("SELECT * FROM mensagens WHERE id = ?", (cursor.lastrowid,))[0])

    def excluir_mensagem(self, chat_id: int, mensagem_id: int) -> None:
        """Apaga uma mensagem (usado para desfazer a pergunta quando o modelo falha)."""
        with self.db.transaction():
            if self.db.executar("DELETE FROM mensagens WHERE id = ? AND chat_id = ?", (mensagem_id, chat_id)).rowcount == 0:
                raise ChatNaoEncontrado(f"A mensagem {mensagem_id} não existe no chat {chat_id}.")

    def listar_mensagens(self, chat_id: int) -> List[MensagemChat]:
        self.obter_chat(chat_id)
        linhas = self.db.consultar("SELECT * FROM mensagens WHERE chat_id = ? ORDER BY ordem", (chat_id,))
        return [_mensagem(linha) for linha in linhas]

    def contar_mensagens(self, chat_id: int) -> int:
        return self.db.valor("SELECT COUNT(*) FROM mensagens WHERE chat_id = ?", (chat_id,))

    # ---------- internos ----------
    def _atualizar(self, sql: str, parametros: tuple, chat_id: int) -> None:
        with self.db.transaction():
            if self.db.executar(sql, parametros).rowcount == 0:
                raise ChatNaoEncontrado(f"O chat {chat_id} não existe.")

    @staticmethod
    def _validar_modo(modo: str) -> None:
        if modo not in MODOS:
            raise ValueError(f"Modo inválido: {modo!r} (use um de {', '.join(MODOS)}).")