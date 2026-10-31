"""
Apresentação (sem Qt)
---------------------
Decide COMO cada mensagem aparece na tela: autor, estilo da bolha e rodapé (fontes, métricas, estado
de combate). Fica separado dos widgets para poder ser testado sem abrir janela.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from rpgassistant.core.models import (
    PAPEL_SISTEMA, PAPEL_USUARIO, TIPO_AJUDA, TIPO_AVISO, TIPO_FEEDBACK, Chat, MensagemChat,
)
from rpgassistant.core.modos import MODO_ASSISTENTE, MODO_JOGADOR, MODO_MESTRE

EMOJI_MODO = {MODO_ASSISTENTE: "🧙", MODO_MESTRE: "🗺️", MODO_JOGADOR: "⚔️"}
ROTULO_MODO = {
    MODO_ASSISTENTE: "Assistente",
    MODO_MESTRE: "Mestre (a IA narra)",
    MODO_JOGADOR: "Jogador (a IA joga)",
}

ESTILO_USUARIO = "usuario"
ESTILO_ASSISTENTE = "assistente"
ESTILO_AVISO = "aviso"
ESTILO_AJUDA = "ajuda"
ESTILO_FEEDBACK = "feedback"
ESTILO_RECUSA = "recusa"
ESTILO_ERRO = "erro"


@dataclass(frozen=True)
class Bolha:
    """O que a tela precisa para desenhar uma mensagem."""

    estilo: str
    autor: str
    texto: str
    rodape: str = ""


def autor_da_ia(modo: Optional[str], nome_jogador: Optional[str] = None) -> str:
    if modo == MODO_MESTRE:
        return "🗺️ Mestre"
    if modo == MODO_JOGADOR:
        return f"⚔️ {nome_jogador}" if nome_jogador else "⚔️ Jogador IA"
    if modo == MODO_ASSISTENTE:
        return "🧙 Assistente"
    return "🎲 RPG AI Assistant"


def autor_do_usuario(modo: Optional[str]) -> str:
    return "Você (Mestre)" if modo == MODO_JOGADOR else "Você"


def selo_do_modo(modo: Optional[str]) -> str:
    """Texto do selo no cabeçalho do chat."""
    if modo is None:
        return "Escolha o modo"
    return f"{EMOJI_MODO[modo]} {ROTULO_MODO[modo]}"


def titulo_do_chat(chat: Chat) -> str:
    """Texto do chat na lista lateral: emoji do modo e título."""
    return f"{EMOJI_MODO.get(chat.modo, '💬')}  {chat.titulo}"


def markdown_para_exibir(texto: str) -> str:
    """
    O modelo separa linhas com um único \\n, que o Markdown junta numa linha só. Aqui cada quebra simples
    vira uma quebra de verdade, preservando o formato da resposta (parágrafos e listas continuam iguais).
    """
    return re.sub(r"(?<!\n)\n(?!\n)", "  \n", texto)


def _rodape(extras: dict) -> str:
    partes = []
    if extras.get("estado"):
        partes.append(f"⚔️ Estado do combate: {extras['estado']}")
    if extras.get("fontes"):
        partes.append(f"📚 {extras['fontes']}")
    if extras.get("metricas"):
        partes.append(str(extras["metricas"]))
    return "\n".join(partes)


def descrever_mensagem(msg: MensagemChat, modo: Optional[str], nome_jogador: Optional[str] = None) -> Bolha:
    """Estilo, autor e rodapé de uma mensagem salva."""
    if msg.tipo == TIPO_FEEDBACK:
        return Bolha(ESTILO_FEEDBACK, "📝 Mentor", msg.conteudo)
    if msg.papel == PAPEL_USUARIO:
        return Bolha(ESTILO_USUARIO, autor_do_usuario(modo), msg.conteudo)
    if msg.papel == PAPEL_SISTEMA:
        return Bolha(ESTILO_AJUDA if msg.tipo == TIPO_AJUDA else ESTILO_AVISO, "", msg.conteudo)
    # papel do assistente
    autor = autor_da_ia(modo, nome_jogador)
    if msg.extras.get("recusada"):
        return Bolha(ESTILO_RECUSA, autor, msg.conteudo, str(msg.extras.get("metricas", "")))
    if msg.tipo == TIPO_AJUDA:
        return Bolha(ESTILO_AJUDA, "", msg.conteudo)
    if msg.tipo == TIPO_AVISO:
        return Bolha(ESTILO_AVISO, autor, msg.conteudo)
    return Bolha(ESTILO_ASSISTENTE, autor, msg.conteudo, _rodape(msg.extras))


def bolha_de_erro(texto: str) -> Bolha:
    return Bolha(ESTILO_ERRO, "", f"⚠️ {texto}")


def resumo_sessao(chat: Chat, configurar: bool) -> List[str]:
    """Linhas do painel de sessão, abaixo do cabeçalho do chat."""
    estado = chat.estado
    if chat.modo == MODO_ASSISTENTE:
        return ["Respondo apenas com o que está nos livros indexados."]
    if chat.modo == MODO_MESTRE:
        if configurar:
            return ["Falta configurar a aventura (cenário e ficha)."]
        linhas = [f"🏰 {estado.get('cenario', '')}", f"🛡️ {estado.get('personagem', '')}"]
        if estado.get("estado_combate"):
            linhas.append(f"⚔️ {estado['estado_combate']}")
        return linhas
    if chat.modo == MODO_JOGADOR:
        if configurar:
            return ["Falta definir o personagem e o perfil do jogador."]
        return [f"🛡️ {estado.get('ficha', '')}"]
    return []