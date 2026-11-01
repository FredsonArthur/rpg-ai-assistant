"""
Modos de uso
------------
Os três modos de um chat (Assistente, Mestre e Jogador) e a leitura de pedidos em linguagem natural,
como "seja meu mestre" ou "quero ser o mestre", usada na primeira mensagem de cada chat.
"""

import re
import unicodedata
from typing import List, Optional

MODO_ASSISTENTE = "assistente"
MODO_MESTRE = "mestre"
MODO_JOGADOR = "jogador"
MODOS = [MODO_ASSISTENTE, MODO_MESTRE, MODO_JOGADOR]

ROTULOS_MODO = {
    MODO_ASSISTENTE: "🧙 Assistente",
    MODO_MESTRE: "🗺️ Mestre (a IA narra)",
    MODO_JOGADOR: "⚔️ Jogador (a IA joga)",
}

LIMITE_TEXTO_PEDIDO = 200  # pedidos de troca de modo são frases curtas

_MESTRE = r"(?:mestre|narrador|dm|gm|game ?master|dungeon ?master)"
_JOGADOR = r"(?:jogador|personagem jogador|pj|player)"
_ARTIGOS = r"(?:como\s+|de\s+|o\s+papel\s+de\s+|o\s+|a\s+|um\s+|uma\s+|meu\s+|minha\s+)*"
_VERBOS_PAPEL = r"(?:seja|atue|aja|assuma|vire|fique|faca|jogue|conduza)"


def _pedido_ia_assumir(papel: str) -> List[str]:
    """Frases em que o usuário pede que a IA assuma o papel (Mestre ou Jogador)."""
    return [
        rf"\b(?:quero|queria|preciso|gostaria)\s+que\s+(?:voce|vc|tu)\s+{_VERBOS_PAPEL}\b.{{0,40}}\b{papel}\b",
        rf"\b{_VERBOS_PAPEL}\s+{_ARTIGOS}{papel}\b",
        rf"\b(?:pode|poderia|consegue|podia)\s+(?:ser|atuar|agir|virar|fazer)\s+{_ARTIGOS}{papel}\b",
        rf"\b(?:voce|vc)\s+(?:sera|vai\s+ser)\s+{_ARTIGOS}{papel}\b",
    ]


_PEDIDOS_MESTRE = _pedido_ia_assumir(_MESTRE)
# Pedidos mais vagos (ignorados se forem perguntas, ex.: "quero jogar uma partida, como funciona a iniciativa?")
_PEDIDOS_MESTRE_VAGOS = [
    rf"\b(?:vamos|bora|quero|queria|podemos)\s+(?:jogar|comecar|iniciar|fazer)\b.{{0,40}}\b(?:aventura|campanha|sessao|partida)\b",
    rf"\b(?:inicie|comece|monte|conduza)\s+(?:uma?\s+)?(?:aventura|campanha|sessao)\b",
]
# Frases em que o usuário diz que ele quer ser o Mestre/Jogador (também ignoradas se forem perguntas)
_EU_JOGADOR = [rf"\b(?:quero|vou|vamos)\s+(?:ser|fazer\s+o\s+papel\s+de)\s+{_ARTIGOS}{_JOGADOR}\b"]
_EU_MESTRE = [
    rf"\b(?:quero|vou|vamos)\s+(?:ser|mestrar|fazer\s+o\s+papel\s+de)\s+{_ARTIGOS}{_MESTRE}\b",
    r"\b(?:eu|vou|quero|queria|vamos)\s+mestrar\b",
    rf"\bquero\s+treinar\s+(?:como\s+)?{_MESTRE}\b",
]
_PEDIDOS_JOGADOR = _pedido_ia_assumir(_JOGADOR)

def normalizar(texto: str) -> str:
    """Minúsculas e sem acentos, para comparar com os padrões."""
    decomposto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn")


def _casa(padroes: List[str], texto: str) -> bool:
    return any(re.search(p, texto) for p in padroes)


def detectar_pedido_de_modo(texto: str) -> Optional[str]:
    """
    Lê um pedido em linguagem natural e devolve o modo pedido, ou None se não houver pedido (ou se houver
    pedidos contraditórios). Frases longas, que não parecem um pedido, são ignoradas, e perguntas não
    contam como declaração ("Quero ser mestre, por onde começar?" é uma dúvida, não um pedido).
    """
    bruto = texto.strip()
    if len(bruto) > LIMITE_TEXTO_PEDIDO:
        return None
    normal = normalizar(bruto)

    eh_pergunta = "?" in bruto
    quer_mestre = _casa(_PEDIDOS_MESTRE, normal) or (
        not eh_pergunta and (_casa(_PEDIDOS_MESTRE_VAGOS, normal) or _casa(_EU_JOGADOR, normal)))
    quer_jogador = _casa(_PEDIDOS_JOGADOR, normal) or (not eh_pergunta and _casa(_EU_MESTRE, normal))

    if quer_mestre and not quer_jogador:
        return MODO_MESTRE
    if quer_jogador and not quer_mestre:
        return MODO_JOGADOR
    return None