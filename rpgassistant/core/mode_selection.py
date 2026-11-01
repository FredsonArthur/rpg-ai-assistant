"""
Escolha do modo na primeira mensagem
------------------------------------
Todo chat novo começa sem modo: a primeira mensagem do usuário diz se ele quer o Assistente, o Mestre
ou o Jogador. Aceita o número da opção (1, 2 ou 3), o nome do modo, um comando (/mestre) ou um pedido
em linguagem natural ("seja meu mestre"). Uma pergunta clara, como "Como funciona agarrar?", escolhe o
Assistente automaticamente. Se não der para saber, o app repete as opções.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from rpgassistant.core.modos import (
    MODO_ASSISTENTE, MODO_JOGADOR, MODO_MESTRE, detectar_pedido_de_modo, normalizar,
)

MSG_BOAS_VINDAS = """Como você quer usar o assistente? Escolha digitando o número ou o nome:

1. **Assistente**: tiro dúvidas de regras e lore e crio NPCs, encontros e itens, sempre com base nos livros que tenho.
2. **Mestre**: eu conduzo uma aventura e você joga.
3. **Jogador**: você é o Mestre e eu interpreto um personagem.

Também vale fazer uma pergunta de regras direto (ela abre o modo Assistente) ou escrever, por exemplo, "quero que você seja meu mestre"."""

MSG_REPETIR = """Não entendi qual modo você quer. Digite **1** (Assistente), **2** (Mestre) ou **3** (Jogador), ou faça uma pergunta de regras para abrir o modo Assistente."""

_OPCOES = {"1": MODO_ASSISTENTE, "assistente": MODO_ASSISTENTE,
           "2": MODO_MESTRE, "mestre": MODO_MESTRE,
           "3": MODO_JOGADOR, "jogador": MODO_JOGADOR}
_RE_OPCAO = re.compile(r"^(?:(?:quero|escolho|opcao|modo)\s+)?(?:(?:o|a|um|uma)\s+)?(assistente|mestre|jogador|1|2|3)$")

_COMECOS_DE_PERGUNTA = (
    "como", "o que", "oque", "qual", "quais", "quando", "onde", "quem", "por que", "porque", "quanto",
    "quantos", "quantas", "posso", "pode", "podem", "existe", "existem", "ha ", "explique", "explica",
    "me explique", "descreva", "liste", "defina", "diga", "me diga", "crie", "cria", "gere", "monte",
    "sugira", "ajude", "me ajude", "resuma", "compare", "quero saber", "gostaria de saber", "preciso saber",
)


@dataclass(frozen=True)
class Escolha:
    """Resultado da leitura da primeira mensagem."""

    modo: Optional[str]      # None quando não ficou claro
    pergunta: bool = False   # True: a mensagem é uma pergunta que o Assistente deve responder
    ajuda: bool = False      # True: o usuário pediu /ajuda


def parece_pergunta(texto: str) -> bool:
    """Heurística: tem interrogação ou começa como uma pergunta ou um pedido ("como", "explique", "crie"...)."""
    if "?" in texto:
        return len(texto.strip()) >= 2
    normal = normalizar(texto).strip()
    return any(normal == c.strip() or normal.startswith(c if c.endswith(" ") else c + " ")
               for c in _COMECOS_DE_PERGUNTA)


def escolher_modo(texto: str) -> Escolha:
    """Interpreta a primeira mensagem de um chat."""
    normal = normalizar(texto).strip()

    if normal.startswith("/"):
        comando = normal.split()[0]
        modo = {"/assistente": MODO_ASSISTENTE, "/mestre": MODO_MESTRE, "/jogador": MODO_JOGADOR}.get(comando)
        return Escolha(modo) if modo else Escolha(None, ajuda=True)

    opcao = _RE_OPCAO.match(re.sub(r"[^\w\s]", " ", normal).strip())
    if opcao:
        return Escolha(_OPCOES[opcao.group(1)])

    pedido = detectar_pedido_de_modo(texto)
    if pedido:
        return Escolha(pedido)

    if parece_pergunta(texto):
        return Escolha(MODO_ASSISTENTE, pergunta=True)
    return Escolha(None)