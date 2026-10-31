"""
Gerenciador de chats
--------------------
Parte do núcleo que cuida da lista de conversas: criar, abrir, renomear, excluir e restaurar
o último chat ao reabrir o app. Tudo é salvo no banco a cada operação, então fechar o app a
qualquer momento não perde nada. Não conhece a interface gráfica.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from rpgassistant import config
from rpgassistant.core.historico import Historico
from rpgassistant.core.models import (
    PAPEL_ASSISTENTE, PAPEL_USUARIO, TIPO_FALA, TITULO_PADRAO, Chat, MensagemChat, gerar_titulo,
)
from rpgassistant.errors import ChatNaoEncontrado, ModoJaDefinidoError
from rpgassistant.storage.database import Database
from rpgassistant.storage.repository import RepositorioChats

logger = logging.getLogger(__name__)


def para_historico(mensagens: Sequence[MensagemChat]) -> Historico:
    """
    Converte as mensagens salvas no histórico enviado ao modelo: só as falas do usuário e do
    assistente. Avisos, ajuda e feedback ficam no chat, mas nunca vão ao modelo.
    """
    return [
        {"role": m.papel, "content": m.conteudo}
        for m in mensagens
        if m.tipo == TIPO_FALA and m.papel in (PAPEL_USUARIO, PAPEL_ASSISTENTE)
    ]


class GerenciadorDeChats:
    def __init__(self, repositorio: RepositorioChats) -> None:
        self.repositorio = repositorio
        self._atual_id: Optional[int] = None

    @classmethod
    def abrir(cls, caminho: Union[str, Path, None] = None) -> "GerenciadorDeChats":
        """Abre o banco de chats (por padrão, o definido na configuração) e devolve o gerenciador."""
        return cls(RepositorioChats(Database(caminho if caminho is not None else config.settings.chats_db)))

    def fechar(self) -> None:
        self.repositorio.db.fechar()

    # ---------- lista e chat atual ----------
    @property
    def chat_atual(self) -> Optional[Chat]:
        if self._atual_id is None:
            return None
        try:
            return self.repositorio.obter_chat(self._atual_id)
        except ChatNaoEncontrado:
            self._atual_id = None
            return None

    def listar(self) -> List[Chat]:
        return self.repositorio.listar_chats()

    def restaurar_ultimo(self) -> Optional[Chat]:
        """Ao abrir o app: volta ao chat usado por último, ou None se ainda não há chats."""
        chats = self.listar()
        self._atual_id = chats[0].id if chats else None
        return chats[0] if chats else None

    def abrir_chat(self, chat_id: int) -> Chat:
        chat = self.repositorio.obter_chat(chat_id)
        self._atual_id = chat.id
        return chat

    def novo_chat(self) -> Chat:
        """
        Cria um chat e o torna o atual. Se já existe um chat em branco (sem modo e sem nenhuma mensagem do
        usuário; as boas-vindas não contam), reaproveita-o, para a lista não se encher de chats vazios.
        """
        for chat in self.listar():
            if chat.modo is None and not any(m.papel == PAPEL_USUARIO for m in self.mensagens(chat.id)):
                self._atual_id = chat.id
                return chat
        chat = self.repositorio.criar_chat()
        self._atual_id = chat.id
        return chat

    def renomear(self, chat_id: int, titulo: str) -> Chat:
        return self.repositorio.renomear_chat(chat_id, titulo)

    def excluir(self, chat_id: int) -> Optional[Chat]:
        """Exclui o chat. Se era o atual, abre o mais recente que sobrou (ou nenhum) e o devolve."""
        self.repositorio.excluir_chat(chat_id)
        if self._atual_id == chat_id:
            return self.restaurar_ultimo()
        return self.chat_atual

    # ---------- modo, título e estado ----------
    def definir_modo(self, chat_id: int, modo: str) -> Chat:
        """Define o modo do chat. Só pode ser escolhido uma vez: repetir o mesmo modo não faz nada."""
        chat = self.repositorio.obter_chat(chat_id)
        if chat.modo is not None:
            if chat.modo == modo:
                return chat
            raise ModoJaDefinidoError(
                f"Este chat já está no modo {chat.modo}. Para usar outro modo, abra um novo chat."
            )
        return self.repositorio.definir_modo(chat_id, modo)

    def titulo_automatico(self, chat_id: int, texto: str) -> Chat:
        """Dá ao chat um título a partir de `texto`, mas só se ele ainda tiver o título padrão."""
        chat = self.repositorio.obter_chat(chat_id)
        if chat.titulo != TITULO_PADRAO:
            return chat
        return self.repositorio.renomear_chat(chat_id, gerar_titulo(texto))

    def estado(self, chat_id: int) -> Dict[str, Any]:
        return dict(self.repositorio.obter_chat(chat_id).estado)

    def atualizar_estado(self, chat_id: int, **campos: Any) -> Dict[str, Any]:
        """Mescla `campos` no estado da sessão (cenário, ficha, estado de combate...) e salva."""
        novo = {**self.repositorio.obter_chat(chat_id).estado, **campos}
        return dict(self.repositorio.salvar_estado(chat_id, novo).estado)

    # ---------- mensagens ----------
    def registrar(self, chat_id: int, papel: str, conteudo: str, tipo: str = TIPO_FALA,
                  extras: Optional[Dict[str, Any]] = None) -> MensagemChat:
        return self.repositorio.adicionar_mensagem(chat_id, papel, conteudo, tipo, extras)

    def descartar(self, mensagem: MensagemChat) -> None:
        """Desfaz uma mensagem já salva (a pergunta cuja resposta falhou não deve ficar no histórico)."""
        self.repositorio.excluir_mensagem(mensagem.chat_id, mensagem.id)

    def mensagens(self, chat_id: int) -> List[MensagemChat]:
        return self.repositorio.listar_mensagens(chat_id)

    def historico_para_llm(self, chat_id: int) -> Historico:
        return para_historico(self.mensagens(chat_id))