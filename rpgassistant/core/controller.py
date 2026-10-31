"""
Controlador de chat
-------------------
Toda a lógica de uma conversa, sem interface: escolher o modo na primeira mensagem, configurar a
aventura ou o personagem, responder em cada modo (Assistente "só os livros", Mestre, Jogador), gerar
o feedback e salvar tudo no banco. A janela só exibe o que este controlador devolve.

O resultado de cada ação é um `Turno`. Mensagens que não precisam do modelo (avisos, recusas,
saudações) já vêm salvas; quando o modelo é necessário, itere `turno.tokens()` (de preferência fora da
thread da interface) e depois chame `turno.concluir()` para gravar a resposta.
Depois de `concluir()`, a janela deve recarregar as mensagens do chat: se o modelo recusar a pergunta, a
pergunta que estava salva é trocada por um aviso.
"""

from __future__ import annotations

import logging
from typing import Callable, Iterator, List, Optional

from rpgassistant.core import policy
from rpgassistant.core.chats import GerenciadorDeChats
from rpgassistant.core.mode_selection import MSG_BOAS_VINDAS, MSG_REPETIR, escolher_modo
from rpgassistant.core.models import (
    PAPEL_ASSISTENTE, PAPEL_SISTEMA, PAPEL_USUARIO, TIPO_AJUDA, TIPO_AVISO, TIPO_FEEDBACK,
    Chat, MensagemChat,
)
from rpgassistant.core.modos import MODO_ASSISTENTE, MODO_JOGADOR, MODO_MESTRE, ROTULOS_MODO, normalizar
from rpgassistant.errors import BaseVaziaError, ModoJaDefinidoError, OllamaError
from rpgassistant.modes import assistente, jogador, mestre

logger = logging.getLogger(__name__)

FASE_ESCOLHER_MODO = "escolher_modo"
FASE_CONFIGURAR = "configurar"
FASE_CONVERSA = "conversa"

# Chaves do estado salvo no chat
CENARIO, PERSONAGEM, ESTADO_COMBATE = "cenario", "personagem", "estado_combate"
NOME, FICHA, ARQUETIPO, ARQUETIPO_TEXTO = "nome", "ficha", "arquetipo", "arquetipo_texto"

AJUDA_CHAT = """**Como usar**
- Cada chat tem um modo fixo (Assistente, Mestre ou Jogador), escolhido na primeira mensagem. Para usar outro modo, abra um novo chat.
- `/ajuda`: mostra esta ajuda.
- `/feedback`: no modo Jogador, a IA sai do personagem e analisa a sua condução como Mestre."""

_MSG_MODO_ATIVADO = {
    MODO_ASSISTENTE: "Modo **Assistente** ativado. Pergunte sobre regras e lore, ou peça NPCs, encontros e itens. "
                     "Respondo apenas com o que está nos livros que tenho.",
    MODO_MESTRE: "Modo **Mestre** ativado. Escolha o cenário e a sua ficha para eu abrir a aventura.",
    MODO_JOGADOR: "Modo **Jogador** ativado. Defina o personagem que vou interpretar e o perfil de jogador.",
}


class Turno:
    """
    Resultado de uma ação do usuário. `salvas` são as mensagens já gravadas. Se houver trabalho com o
    modelo, `tokens()` o executa e entrega o texto aos poucos (a cada pedaço, `texto_visivel` diz o que
    mostrar), e `concluir()` grava a resposta final. Se o modelo falhar, a pergunta é desfeita.
    """

    def __init__(self, salvas: Optional[List[MensagemChat]] = None,
                 produzir: Optional[Callable[[], Iterator[str]]] = None,
                 concluir: Optional[Callable[[str], MensagemChat]] = None,
                 descartar: Optional[Callable[[], None]] = None,
                 visivel: Optional[Callable[[str], str]] = None) -> None:
        self.salvas: List[MensagemChat] = list(salvas or [])
        self._produzir = produzir
        self._concluir = concluir
        self._descartar = descartar
        self._visivel = visivel or (lambda texto: texto)
        self.texto = ""
        self.resposta: Optional[MensagemChat] = None

    @property
    def precisa_modelo(self) -> bool:
        return self._produzir is not None

    def texto_visivel(self) -> str:
        """O texto acumulado, já ajustado para exibição (sem a sentinela nem a linha de estado)."""
        return self._visivel(self.texto)

    def tokens(self) -> Iterator[str]:
        if self._produzir is None:
            return
        try:
            for parte in self._produzir():
                self.texto += parte
                yield parte
        except OllamaError:
            self._desfazer()
            raise

    def cancelar(self) -> None:
        """O usuário apertou Parar: desfaz a pergunta salva, como se o modelo tivesse falhado."""
        self._desfazer()

    def concluir(self) -> Optional[MensagemChat]:
        """Grava a resposta final. Devolve a mensagem salva (ou None se o turno não tinha modelo)."""
        if self._concluir is None:
            return None
        try:
            self.resposta = self._concluir(self.texto)
        except OllamaError:
            self._desfazer()
            raise
        return self.resposta

    def _desfazer(self) -> None:
        if self._descartar is not None:
            self._descartar()
            self._descartar = None


class ControladorDeChat:
    def __init__(self, gerenciador: GerenciadorDeChats) -> None:
        self.chats = gerenciador

    # ---------- estado do chat ----------
    def fase(self, chat_id: int) -> str:
        chat = self.chats.repositorio.obter_chat(chat_id)
        if chat.modo is None:
            return FASE_ESCOLHER_MODO
        if chat.modo == MODO_MESTRE and CENARIO not in chat.estado:
            return FASE_CONFIGURAR
        if chat.modo == MODO_JOGADOR and FICHA not in chat.estado:
            return FASE_CONFIGURAR
        return FASE_CONVERSA

    def boas_vindas(self, chat_id: int) -> Optional[MensagemChat]:
        """Mostra o menu de modos em um chat ainda vazio. Não faz nada se o chat já tem mensagens."""
        if self.chats.mensagens(chat_id):
            return None
        return self.chats.registrar(chat_id, PAPEL_ASSISTENTE, MSG_BOAS_VINDAS, TIPO_AVISO)

    # ---------- mensagem do usuário ----------
    def enviar(self, chat_id: int, texto: str) -> Turno:
        texto = texto.strip()
        if not texto:
            raise ValueError("A mensagem está vazia.")
        chat = self.chats.repositorio.obter_chat(chat_id)
        fase = self.fase(chat_id)
        comando = normalizar(texto).split()[0] if texto.startswith("/") else ""

        if comando == "/ajuda":
            return self._local(chat_id, (PAPEL_USUARIO, texto, TIPO_AVISO), (PAPEL_ASSISTENTE, AJUDA_CHAT, TIPO_AJUDA))
        if fase == FASE_ESCOLHER_MODO:
            return self._primeira_mensagem(chat, texto)
        if fase == FASE_CONFIGURAR:
            return self._local(chat_id, (PAPEL_ASSISTENTE, "Termine a configuração acima para começarmos.", TIPO_AVISO))
        if comando == "/feedback":
            return self.feedback(chat_id)
        if comando:
            return self._comando_de_modo(chat, texto, comando)

        if chat.modo == MODO_ASSISTENTE:
            return self._assistente(chat, texto)
        if chat.modo == MODO_MESTRE:
            return self._mestre(chat, texto)
        return self._jogador(chat, texto)

    def _comando_de_modo(self, chat: Chat, texto: str, comando: str) -> Turno:
        novo = {"/assistente": MODO_ASSISTENTE, "/mestre": MODO_MESTRE, "/jogador": MODO_JOGADOR}.get(comando)
        if novo is None:
            return self._local(chat.id, (PAPEL_USUARIO, texto, TIPO_AVISO), (PAPEL_ASSISTENTE, AJUDA_CHAT, TIPO_AJUDA))
        if novo == chat.modo:
            aviso = f"Este chat já está no modo {ROTULOS_MODO[novo]}."
        else:
            aviso = (f"Este chat está no modo {ROTULOS_MODO[chat.modo]} e não muda de modo. "
                     "Para usar outro modo, abra um novo chat.")
        return self._local(chat.id, (PAPEL_USUARIO, texto, TIPO_AVISO), (PAPEL_ASSISTENTE, aviso, TIPO_AVISO))

    def _primeira_mensagem(self, chat: Chat, texto: str) -> Turno:
        escolha = escolher_modo(texto)
        if escolha.ajuda:
            return self._local(chat.id, (PAPEL_USUARIO, texto, TIPO_AVISO), (PAPEL_ASSISTENTE, MSG_BOAS_VINDAS, TIPO_AVISO))
        if escolha.modo is None:
            return self._local(chat.id, (PAPEL_USUARIO, texto, TIPO_AVISO), (PAPEL_ASSISTENTE, MSG_REPETIR, TIPO_AVISO))

        self.chats.definir_modo(chat.id, escolha.modo)
        if escolha.pergunta:  # a primeira mensagem já é uma pergunta de regras: responda
            return self._assistente(self.chats.repositorio.obter_chat(chat.id), texto)
        return self._local(chat.id, (PAPEL_USUARIO, texto, TIPO_AVISO),
                           (PAPEL_ASSISTENTE, _MSG_MODO_ATIVADO[escolha.modo], TIPO_AVISO))

    # ---------- Assistente: só os livros ----------
    def _assistente(self, chat: Chat, texto: str) -> Turno:
        historico = self.chats.historico_para_llm(chat.id)
        try:
            consulta = assistente.preparar(texto, historico)
        except BaseVaziaError as e:
            return self._local(chat.id, (PAPEL_USUARIO, texto, TIPO_AVISO), (PAPEL_ASSISTENTE, str(e), TIPO_AVISO))

        self.chats.titulo_automatico(chat.id, texto)
        if consulta.recusada:
            return self._recusa(chat.id, texto, {"recusada": True, "metricas": consulta.motivo_recusa})

        usuario = self.chats.registrar(chat.id, PAPEL_USUARIO, texto)
        try:
            stream = assistente.iniciar_stream(consulta)
        except OllamaError:
            self.chats.descartar(usuario)
            raise

        def concluir(bruto: str) -> MensagemChat:
            if not bruto.strip():
                raise OllamaError("O modelo não devolveu texto. Tente de novo.")
            if policy.eh_recusa_do_modelo(bruto):
                self.chats.descartar(usuario)  # a pergunta recusada não entra no histórico do modelo
                return self._recusa(chat.id, texto, {"recusada": True, "metricas": "O modelo não encontrou a resposta nos trechos."}).salvas[-1]
            metricas = assistente.formatar_metricas(stream.prompt_tokens, stream.completion_tokens,
                                                    consulta.consulta_busca, texto)
            return self.chats.registrar(chat.id, PAPEL_ASSISTENTE, bruto.strip(),
                                        extras={"fontes": consulta.fontes, "metricas": metricas})

        return Turno([usuario], stream.tokens, concluir, lambda: self.chats.descartar(usuario), policy.texto_visivel)

    def _recusa(self, chat_id: int, pergunta: str, extras: dict) -> Turno:
        """A pergunta e a recusa ficam no chat, mas fora do histórico enviado ao modelo."""
        return self._local(chat_id, (PAPEL_USUARIO, pergunta, TIPO_AVISO),
                           (PAPEL_ASSISTENTE, policy.RECUSA, TIPO_AVISO, extras))

    # ---------- Mestre ----------
    def configurar_mestre(self, chat_id: int, cenario: str, personagem: str = "") -> Turno:
        """Abre a aventura: o Mestre narra a cena inicial. Nada é salvo se o modelo falhar."""
        self._exigir_configuracao(chat_id, MODO_MESTRE)
        cenario = cenario.strip()
        if not cenario:
            raise ValueError("Escolha ou descreva um cenário para a aventura.")
        personagem = personagem.strip() or mestre.FICHA_GENERICA
        pedido = (f"Quero começar a aventura no cenário '{cenario}' com meu personagem '{personagem}'. "
                  "Dê a introdução imersiva e faça a primeira pergunta de ação.")
        stream, fontes = mestre.run_master_turn_stream(pedido, cenario, personagem, [], "")

        def concluir(bruto: str) -> MensagemChat:
            fala, estado = mestre.extrair_estado(bruto, "")
            if not fala.strip():
                raise OllamaError("O modelo não devolveu texto. Tente de novo.")
            self.chats.atualizar_estado(chat_id, **{CENARIO: cenario, PERSONAGEM: personagem, ESTADO_COMBATE: estado})
            self.chats.titulo_automatico(chat_id, cenario)
            self.chats.registrar(chat_id, PAPEL_SISTEMA, f"🗺️ Nova aventura: {cenario}, com {personagem}.", TIPO_AVISO)
            return self.chats.registrar(chat_id, PAPEL_ASSISTENTE, fala, extras={"estado": estado, "fontes": fontes})

        return Turno(None, stream.tokens, concluir, None, mestre.ocultar_linha_estado)

    def _mestre(self, chat: Chat, texto: str) -> Turno:
        estado = self.chats.estado(chat.id)
        historico = self.chats.historico_para_llm(chat.id)
        usuario = self.chats.registrar(chat.id, PAPEL_USUARIO, texto)
        try:
            stream, fontes = mestre.run_master_turn_stream(
                texto, estado[CENARIO], estado[PERSONAGEM], historico, estado.get(ESTADO_COMBATE, ""))
        except OllamaError:
            self.chats.descartar(usuario)
            raise

        def concluir(bruto: str) -> MensagemChat:
            fala, novo_estado = mestre.extrair_estado(bruto, estado.get(ESTADO_COMBATE, ""))
            if not fala.strip():
                raise OllamaError("O modelo não devolveu texto. Tente de novo.")
            self.chats.atualizar_estado(chat.id, **{ESTADO_COMBATE: novo_estado})
            return self.chats.registrar(chat.id, PAPEL_ASSISTENTE, fala, extras={"estado": novo_estado, "fontes": fontes})

        return Turno([usuario], stream.tokens, concluir, lambda: self.chats.descartar(usuario), mestre.ocultar_linha_estado)

    # ---------- Jogador ----------
    def configurar_jogador(self, chat_id: int, nome: str, descricao: str, arquetipo: str,
                           arquetipo_texto: str = "") -> Turno:
        """Coloca o personagem na mesa. A saudação inicial não usa o modelo."""
        self._exigir_configuracao(chat_id, MODO_JOGADOR)
        self._validar_arquetipo(arquetipo)
        nome = nome.strip() or "Aventureiro"
        self.chats.atualizar_estado(chat_id, **{NOME: nome, FICHA: f"{nome}. {descricao.strip()}".strip(),
                                                ARQUETIPO: arquetipo, ARQUETIPO_TEXTO: arquetipo_texto})
        self.chats.titulo_automatico(chat_id, f"{nome} (jogador IA)")
        aviso = self.chats.registrar(chat_id, PAPEL_SISTEMA, f"⚔️ Novo personagem na mesa: {nome} (perfil {arquetipo}).", TIPO_AVISO)
        saudacao = self.chats.registrar(chat_id, PAPEL_ASSISTENTE, jogador.saudacao_inicial(nome, arquetipo))
        return Turno([aviso, saudacao])

    def trocar_arquetipo(self, chat_id: int, arquetipo: str, arquetipo_texto: str = "") -> MensagemChat:
        """Troca o perfil do jogador no meio da sessão, sem perder o histórico."""
        self._validar_arquetipo(arquetipo)
        if self.fase(chat_id) != FASE_CONVERSA or self.chats.repositorio.obter_chat(chat_id).modo != MODO_JOGADOR:
            raise ValueError("O perfil só pode ser trocado em um chat do modo Jogador já configurado.")
        self.chats.atualizar_estado(chat_id, **{ARQUETIPO: arquetipo, ARQUETIPO_TEXTO: arquetipo_texto})
        return self.chats.registrar(chat_id, PAPEL_SISTEMA, f"🔄 Perfil de jogador alterado para {arquetipo}.", TIPO_AVISO)

    def _jogador(self, chat: Chat, texto: str) -> Turno:
        estado = self.chats.estado(chat.id)
        historico = self.chats.historico_para_llm(chat.id)
        usuario = self.chats.registrar(chat.id, PAPEL_USUARIO, texto)

        def produzir() -> Iterator[str]:
            # respostas curtas e com formato a conferir: chamada de uma vez, entregue como um único pedaço
            yield jogador.run_player_simulator_turn(texto, estado[FICHA], historico, estado.get(ARQUETIPO, jogador.ARQUETIPOS_DISPONIVEIS[0]),
                                                    estado.get(ARQUETIPO_TEXTO, ""))

        def concluir(bruto: str) -> MensagemChat:
            if not bruto.strip():
                raise OllamaError("O modelo não devolveu texto. Tente de novo.")
            return self.chats.registrar(chat.id, PAPEL_ASSISTENTE, bruto.strip())

        return Turno([usuario], produzir, concluir, lambda: self.chats.descartar(usuario))

    def feedback(self, chat_id: int) -> Turno:
        """UC09: a IA sai do personagem e analisa a condução do Mestre (o usuário)."""
        chat = self.chats.repositorio.obter_chat(chat_id)
        if chat.modo != MODO_JOGADOR or self.fase(chat_id) != FASE_CONVERSA:
            return self._local(chat_id, (PAPEL_ASSISTENTE, "O feedback só está disponível no modo Jogador, com um personagem em jogo.", TIPO_AVISO))
        historico = self.chats.historico_para_llm(chat_id)
        if not jogador.historico_suficiente(historico):
            return self._local(chat_id, (PAPEL_ASSISTENTE, jogador.AVISO_HISTORICO_CURTO, TIPO_AJUDA))

        def produzir() -> Iterator[str]:
            yield jogador.gerar_feedback(historico)

        def concluir(bruto: str) -> MensagemChat:
            return self.chats.registrar(chat_id, PAPEL_SISTEMA, bruto.strip(), TIPO_FEEDBACK)

        return Turno(None, produzir, concluir)

    # ---------- internos ----------
    def _local(self, chat_id: int, *mensagens: tuple) -> Turno:
        """Turno sem modelo: grava as mensagens (papel, texto, tipo[, extras]) e as devolve."""
        salvas = [self.chats.registrar(chat_id, papel, texto, tipo, (resto[0] if resto else None))
                  for papel, texto, tipo, *resto in mensagens]
        return Turno(salvas)

    def _exigir_configuracao(self, chat_id: int, modo: str) -> None:
        chat = self.chats.repositorio.obter_chat(chat_id)
        if chat.modo != modo:
            raise ModoJaDefinidoError(f"Este chat não está no modo {ROTULOS_MODO[modo]}.")
        if self.fase(chat_id) != FASE_CONFIGURAR:
            raise ValueError("Este chat já está configurado.")

    @staticmethod
    def _validar_arquetipo(arquetipo: str) -> None:
        if arquetipo not in jogador.ARQUETIPOS_DISPONIVEIS:
            raise ValueError(f"Perfil inválido: {arquetipo!r} (use um de {', '.join(jogador.ARQUETIPOS_DISPONIVEIS)}).")