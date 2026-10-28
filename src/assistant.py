"""
Orquestrador do assistente (sem dependência do Streamlit)
---------------------------------------------------------
O app tem um chat único e três modos de uso:

- Assistente: responde dúvidas sobre qualquer assunto (regras e lore de D&D com apoio dos livros).
- Mestre: a IA conduz uma aventura solo e o usuário joga.
- Jogador: o usuário é o Mestre e a IA interpreta um personagem.

Este módulo decide o que o usuário quis dizer (comando, pedido para trocar de modo ou mensagem
comum) e separa o histórico de cada modo para que o Mestre não receba a conversa de regras como
se fosse a história da aventura.
"""

import re
import unicodedata
from dataclasses import dataclass
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

AJUDA = """**Como usar o assistente**
- No modo **Assistente**, pergunte o que quiser: regras, lore, NPCs, encontros, itens... ou qualquer outro assunto.
- Para a IA virar **Mestre**: `/mestre` ou "seja meu mestre". Você joga a aventura.
- Para a IA virar **Jogador**: `/jogador` ou "quero ser o mestre". Você narra e ela responde como personagem.
- `/feedback`: no modo Jogador, a IA analisa a sua condução como Mestre.
- `/assistente`: volta ao modo Assistente (a aventura fica guardada).
- Também dá para trocar de modo pelo menu lateral.

Dentro de uma sessão de Mestre ou Jogador, só os comandos com `/` trocam de modo, para que o que você narra ou faz no jogo nunca seja confundido com um comando."""

LIMITE_TEXTO_PEDIDO = 200  # pedidos de troca de modo são frases curtas

_COMANDOS_MODO = {
    "/assistente": MODO_ASSISTENTE,
    "/mestre": MODO_MESTRE,
    "/jogador": MODO_JOGADOR,
}

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

_VOLTAR = [
    r"\b(?:volte|voltar|volta|retorne|retornar|sair|saia)\b.{0,25}\b(?:assistente|modo\s+normal)\b",
    r"\bmodo\s+assistente\b",
]


@dataclass
class Acao:
    """O que o usuário quis dizer: trocar_modo, ajuda, feedback ou mensagem comum."""
    tipo: str
    modo: Optional[str] = None


def _normalizar(texto: str) -> str:
    """Minúsculas e sem acentos, para comparar com os padrões."""
    decomposto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn")


def _casa(padroes: List[str], texto: str) -> bool:
    return any(re.search(p, texto) for p in padroes)


def interpretar_entrada(texto: str, modo_atual: str) -> Acao:
    """
    Decide o que fazer com o que o usuário digitou.

    - Comandos com "/" valem em qualquer modo.
    - Pedidos em linguagem natural ("seja meu mestre") só valem no modo Assistente: dentro de
      uma sessão de jogo o usuário está narrando ou agindo, e uma fala como "o mestre da guilda
      manda você atuar com cuidado" não pode trocar o modo por engano. A única exceção é pedir
      explicitamente para voltar ao assistente.
    """
    bruto = texto.strip()
    normal = _normalizar(bruto)

    if normal.startswith("/"):
        comando = normal.split()[0]
        if comando in _COMANDOS_MODO:
            return Acao("trocar_modo", _COMANDOS_MODO[comando])
        if comando == "/feedback":
            return Acao("feedback")
        return Acao("ajuda")  # "/ajuda" e comandos desconhecidos

    if modo_atual != MODO_ASSISTENTE:
        if _casa(_VOLTAR, normal):
            return Acao("trocar_modo", MODO_ASSISTENTE)
        return Acao("mensagem")

    if len(bruto) > LIMITE_TEXTO_PEDIDO:
        return Acao("mensagem")

    eh_pergunta = "?" in bruto
    quer_mestre = _casa(_PEDIDOS_MESTRE, normal) or (
        not eh_pergunta and (_casa(_PEDIDOS_MESTRE_VAGOS, normal) or _casa(_EU_JOGADOR, normal)))
    quer_jogador = _casa(_PEDIDOS_JOGADOR, normal) or (not eh_pergunta and _casa(_EU_MESTRE, normal))

    if quer_mestre and not quer_jogador:
        return Acao("trocar_modo", MODO_MESTRE)
    if quer_jogador and not quer_mestre:
        return Acao("trocar_modo", MODO_JOGADOR)
    return Acao("mensagem")  # nenhum pedido, ou pedidos contraditórios


def historico_para_llm(mensagens: List[dict], modo: str, sessao: int) -> List[dict]:
    """
    Monta o histórico enviado ao modelo: só as falas do modo atual e da sessão atual.
    Avisos do sistema (troca de modo, ajuda, feedback) nunca vão ao modelo.
    """
    return [
        {"role": m["role"], "content": m["content"]}
        for m in mensagens
        if m["role"] in ("user", "assistant") and m.get("mode") == modo and m.get("sessao", 0) == sessao
    ]