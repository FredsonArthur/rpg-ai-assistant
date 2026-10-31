"""
Modelos do núcleo
-----------------
Um chat guarda o modo escolhido na primeira mensagem, o estado da sessão (cenário, ficha, estado de
combate, perfil do jogador...) e a lista de mensagens, tudo persistido no banco.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

TITULO_PADRAO = "Novo chat"
LIMITE_TITULO = 60

# Papéis das mensagens. "sistema" são avisos exibidos no chat que nunca vão ao modelo.
PAPEL_USUARIO = "user"
PAPEL_ASSISTENTE = "assistant"
PAPEL_SISTEMA = "sistema"
PAPEIS = (PAPEL_USUARIO, PAPEL_ASSISTENTE, PAPEL_SISTEMA)

# Tipos das mensagens: "fala" é a conversa de verdade; os demais são avisos da interface.
TIPO_FALA = "fala"
TIPO_AVISO = "aviso"
TIPO_AJUDA = "ajuda"
TIPO_FEEDBACK = "feedback"
TIPOS = (TIPO_FALA, TIPO_AVISO, TIPO_AJUDA, TIPO_FEEDBACK)


@dataclass(frozen=True)
class Chat:
    """Uma conversa. `modo` fica None até a primeira mensagem escolher Assistente, Mestre ou Jogador."""

    id: int
    titulo: str
    modo: Optional[str]
    estado: Dict[str, Any]
    criado_em: datetime
    atualizado_em: datetime


@dataclass(frozen=True)
class MensagemChat:
    """Uma mensagem salva. `extras` guarda fontes, métricas e o estado de combate de cada resposta."""

    id: int
    chat_id: int
    ordem: int
    papel: str
    conteudo: str
    tipo: str = TIPO_FALA
    extras: Dict[str, Any] = field(default_factory=dict)
    criado_em: datetime = field(default_factory=datetime.now)


def titulo_valido(titulo: str, limite: int = LIMITE_TITULO) -> str:
    """Limpa um título digitado pelo usuário. Levanta ValueError se ficar vazio."""
    limpo = re.sub(r"\s+", " ", titulo).strip()
    if not limpo:
        raise ValueError("O título do chat não pode ficar vazio.")
    return limpo if len(limpo) <= limite else limpo[: limite - 1].rstrip() + "…"


def gerar_titulo(texto: str, limite: int = LIMITE_TITULO) -> str:
    """Título automático a partir da primeira fala do usuário (ou o padrão, se o texto for vazio)."""
    try:
        return titulo_valido(texto, limite)
    except ValueError:
        return TITULO_PADRAO
    