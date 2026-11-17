"""
Janela principal
----------------
Lista de chats à esquerda e a conversa à direita. Toda a lógica (modo, histórico, respostas, salvamento)
está no ControladorDeChat; esta janela só mostra o que ele devolve e roda o modelo fora da thread da tela.

Ciclo de um turno (uma mensagem enviada, uma configuração ou um feedback):
    _iniciar_turno -> TurnoThread -> sinais (_ao_salvar, _ao_pedaco, _ao_concluir/_ao_falhar/_ao_cancelar)
Ao final de cada turno a tela é redesenhada a partir do banco, que é a fonte da verdade.

Ao fechar a janela, `closeEvent` encerra as threads com cuidado (veja o comentário dele).
"""

from __future__ import annotations

import logging
from typing import Callable, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMenu, QMessageBox, QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from rpgassistant import config
from rpgassistant.core.controller import (
    ARQUETIPO, ARQUETIPO_TEXTO, FASE_CONFIGURAR, NOME, ControladorDeChat, Turno,
)
from rpgassistant.core.models import Chat, MensagemChat
from rpgassistant.core.modos import MODO_JOGADOR, MODO_MESTRE
from rpgassistant.errors import ChatNaoEncontrado
from rpgassistant.modes.jogador import ARQUETIPOS_DISPONIVEIS
from rpgassistant.ui import apresentacao as ap
from rpgassistant.ui.dialogos import DialogoJogador, DialogoMestre
from rpgassistant.ui.estilos import TEMA_ESCURO
from rpgassistant.ui.widgets import AreaConversa, BolhaMensagem, CaixaDeEntrada
from rpgassistant.ui.workers import OllamaThread, TurnoThread

logger = logging.getLogger(__name__)

# Prazos (em milissegundos) usados ao fechar a janela.
ESPERA_TURNO_MS = 10000          # quanto esperar um turno em andamento terminar de forma limpa
ESPERA_OLLAMA_MS = 2000          # quanto esperar a thread que sobe o Ollama
ESPERA_APOS_TERMINAR_MS = 1000   # quanto esperar uma thread depois de encerrada à força


class JanelaPrincipal(QMainWindow):
    """Janela do app: cuida só da tela e delega toda a lógica ao ControladorDeChat."""

    def __init__(self, controlador: ControladorDeChat, iniciar_ollama: bool = True) -> None:
        super().__init__()
        self.ctrl = controlador
        self.chats = controlador.chats

        self._ocupado = False
        self._threads: List[TurnoThread] = []        # guarda as threads até terminarem de verdade
        self._thread_atual: Optional[TurnoThread] = None
        self._ollama_thread: Optional[OllamaThread] = None
        self._bolha_stream: Optional[BolhaMensagem] = None
        self._estilo_stream = ap.ESTILO_ASSISTENTE
        self._autor_stream = ""
        self._texto_a_restaurar = ""                 # a mensagem volta para a caixa se o turno falhar ou for parado
        self._pendentes: List[MensagemChat] = []     # mensagens salvas do turno em andamento que o modelo ainda não respondeu
        self._abrir_config_ao_fim = False
        self._atualizando_painel = False
        self._encerrando = False

        self.setWindowTitle("RPG AI Assistant")
        self.resize(1120, 740)
        self.setStyleSheet(TEMA_ESCURO)
        self._montar_interface()
        self._montar_atalhos()
        self.statusBar().showMessage(f"Modelo local: {config.settings.ollama_model}  ·  funciona sem internet")

        self._abrir_chat_inicial()
        if iniciar_ollama:
            self._iniciar_ollama()

    # ------------------------------------------------------------------ montagem da tela
    @property
    def ocupado(self) -> bool:
        """True enquanto um turno está em andamento (a lista e o painel ficam travados)."""
        return self._ocupado

    def _montar_interface(self) -> None:
        """Divide a janela em duas partes: a lista de chats (esquerda) e a conversa (direita)."""
        divisor = QSplitter(Qt.Orientation.Horizontal)
        divisor.addWidget(self._montar_lateral())
        divisor.addWidget(self._montar_conversa())
        divisor.setChildrenCollapsible(False)
        divisor.setStretchFactor(0, 0)
        divisor.setStretchFactor(1, 1)
        divisor.setSizes([290, 830])
        self.setCentralWidget(divisor)

    def _montar_lateral(self) -> QWidget:
        """Parte esquerda: o botão de novo chat e a lista de conversas."""
        lateral = QWidget()
        lateral.setMinimumWidth(230)
        layout = QVBoxLayout(lateral)
        layout.setContentsMargins(6, 6, 6, 6)

        secao = QLabel("CONVERSAS")
        secao.setObjectName("secao")
        self.btn_novo = QPushButton("＋  Novo chat")
        self.btn_novo.setObjectName("novo")
        self.btn_novo.clicked.connect(self._novo_chat)
        self.lista = QListWidget()
        self.lista.currentRowChanged.connect(self._ao_mudar_linha)
        self.lista.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lista.customContextMenuRequested.connect(self._menu_da_lista)

        layout.addWidget(secao)
        layout.addWidget(self.btn_novo)
        layout.addWidget(self.lista, 1)
        return lateral

    def _montar_conversa(self) -> QWidget:
        """Parte direita: cabeçalho, painel da sessão, área de mensagens e caixa de entrada."""
        conversa = QWidget()
        layout = QVBoxLayout(conversa)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        cabecalho = QHBoxLayout()
        self.titulo = QLabel("")
        self.titulo.setObjectName("titulo")
        self.selo = QLabel("")
        self.selo.setObjectName("selo")
        cabecalho.addWidget(self.titulo, 1)
        cabecalho.addWidget(self.selo)

        # painel da sessão: resumo da aventura/personagem e controles de cada modo
        self.painel = QFrame()
        self.painel.setObjectName("painel")
        painel_layout = QVBoxLayout(self.painel)
        painel_layout.setContentsMargins(12, 8, 12, 8)
        self.lbl_sessao = QLabel("")
        self.lbl_sessao.setWordWrap(True)
        self.btn_config = QPushButton("⚙️  Configurar")
        self.btn_config.clicked.connect(self._configurar)

        self.controles_jogador = QWidget()
        controles = QHBoxLayout(self.controles_jogador)
        controles.setContentsMargins(0, 0, 0, 0)
        self.combo_perfil = QComboBox()
        self.combo_perfil.addItems(ARQUETIPOS_DISPONIVEIS)
        self.combo_perfil.currentTextChanged.connect(lambda _texto: self._ao_trocar_perfil())
        self.edit_perfil = QLineEdit()
        self.edit_perfil.setPlaceholderText("Descreva o perfil personalizado")
        self.edit_perfil.editingFinished.connect(self._ao_trocar_perfil)
        self.btn_feedback = QPushButton("📝  Gerar feedback")
        self.btn_feedback.clicked.connect(self._pedir_feedback)
        controles.addWidget(QLabel("Perfil:"))
        controles.addWidget(self.combo_perfil)
        controles.addWidget(self.edit_perfil, 1)
        controles.addWidget(self.btn_feedback)

        painel_layout.addWidget(self.lbl_sessao)
        painel_layout.addWidget(self.btn_config)
        painel_layout.addWidget(self.controles_jogador)

        self.area = AreaConversa()

        entrada = QHBoxLayout()
        self.entrada = CaixaDeEntrada()
        self.entrada.enviar.connect(self._enviar_do_teclado)
        self.btn_enviar = QPushButton("Enviar")
        self.btn_enviar.setObjectName("enviar")
        self.btn_enviar.clicked.connect(self._enviar_ou_parar)
        entrada.addWidget(self.entrada, 1)
        entrada.addWidget(self.btn_enviar)

        layout.addLayout(cabecalho)
        layout.addWidget(self.painel)
        layout.addWidget(self.area, 1)
        layout.addLayout(entrada)
        return conversa

    def _montar_atalhos(self) -> None:
        """Atalhos de teclado da janela: Ctrl+N (novo chat) e F2 (renomear)."""
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self._novo_chat)
        QShortcut(QKeySequence("F2"), self).activated.connect(self._renomear)

    # ------------------------------------------------------------------ lista de chats
    def _abrir_chat_inicial(self) -> None:
        """Ao abrir o app: volta ao último chat usado ou, se não há nenhum, cria um chat novo."""
        if self.chats.restaurar_ultimo() is None:
            self.chats.novo_chat()
        self._renderizar_chat()

    def _recarregar_lista(self) -> None:
        """Refaz a lista lateral a partir do banco e seleciona o chat atual, sem disparar o sinal de troca."""
        atual = self.chats.chat_atual
        selecionado = None
        self.lista.blockSignals(True)
        self.lista.clear()
        for chat in self.chats.listar():
            item = QListWidgetItem(ap.titulo_do_chat(chat))
            item.setData(Qt.ItemDataRole.UserRole, chat.id)
            self.lista.addItem(item)
            if atual is not None and chat.id == atual.id:
                selecionado = item
        if selecionado is not None:
            self.lista.setCurrentItem(selecionado)
        self.lista.blockSignals(False)

    def _ao_mudar_linha(self, linha: int) -> None:
        """O usuário clicou em outro chat da lista (ignorado enquanto um turno está em andamento)."""
        item = self.lista.item(linha) if linha >= 0 else None
        if item is None or self._ocupado:
            return
        try:
            self.chats.abrir_chat(item.data(Qt.ItemDataRole.UserRole))
        except ChatNaoEncontrado:
            pass  # o chat sumiu; _renderizar_chat mostra o chat atual que sobrou
        self._renderizar_chat()

    def _menu_da_lista(self, posicao) -> None:
        """Menu do botão direito na lista: renomear ou excluir o chat sob o cursor."""
        item = self.lista.itemAt(posicao)
        if item is None or self._ocupado:
            return
        self.chats.abrir_chat(item.data(Qt.ItemDataRole.UserRole))
        self._renderizar_chat()
        menu = QMenu(self)
        renomear = menu.addAction("Renomear (F2)")
        excluir = menu.addAction("Excluir")
        escolhida = menu.exec(self.lista.mapToGlobal(posicao))
        if escolhida == renomear:
            self._renomear()
        elif escolhida == excluir:
            self._excluir()

    def _novo_chat(self) -> None:
        """Abre um chat novo (ou reaproveita o que já está em branco) e põe o foco na caixa de entrada."""
        if self._ocupado:
            return
        self.chats.novo_chat()
        self._renderizar_chat()
        self.entrada.setFocus()

    def _renomear(self) -> None:
        """Pede um novo título para o chat atual e o aplica."""
        chat = self.chats.chat_atual
        if chat is None or self._ocupado:
            return
        texto, confirmou = QInputDialog.getText(self, "Renomear chat", "Novo título:", QLineEdit.EchoMode.Normal, chat.titulo)
        if not confirmou:
            return
        try:
            self.chats.renomear(chat.id, texto)
        except ValueError as e:  # título vazio
            QMessageBox.warning(self, "Renomear chat", str(e))
            return
        self._renderizar_chat()

    def _excluir(self) -> None:
        """Exclui o chat atual, depois de confirmar. Se a lista ficar vazia, cria um chat novo."""
        chat = self.chats.chat_atual
        if chat is None or self._ocupado:
            return
        resposta = QMessageBox.question(
            self, "Excluir chat", f"Excluir “{chat.titulo}” e todas as suas mensagens?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if resposta != QMessageBox.StandardButton.Yes:
            return
        self.chats.excluir(chat.id)
        if self.chats.chat_atual is None and not self.chats.listar():
            self.chats.novo_chat()
        self._renderizar_chat()

    # ------------------------------------------------------------------ conversa
    def _chat_ou_novo(self) -> Chat:
        """O chat atual; se não houver nenhum, restaura o último ou cria um novo."""
        chat = self.chats.chat_atual
        if chat is None:
            chat = self.chats.restaurar_ultimo() or self.chats.novo_chat()
        return chat

    def _renderizar_chat(self, erro: str = "") -> None:
        """Redesenha tudo a partir do banco, que é a fonte da verdade."""
        chat = self._chat_ou_novo()
        self.ctrl.boas_vindas(chat.id)
        chat = self.chats.repositorio.obter_chat(chat.id)
        nome = chat.estado.get(NOME)

        self.area.limpar()
        for mensagem in self.chats.mensagens(chat.id):
            self.area.adicionar(ap.descrever_mensagem(mensagem, chat.modo, nome))
        if erro:
            self.area.adicionar(ap.bolha_de_erro(erro))
        self._bolha_stream = None

        self.titulo.setText(chat.titulo)
        self.selo.setText(ap.selo_do_modo(chat.modo))
        self._atualizar_painel(chat)
        self._recarregar_lista()
        self.area.rolar_para_o_fim()

    def _atualizar_painel(self, chat: Chat) -> None:
        """Mostra ou esconde o resumo da sessão, o botão Configurar e os controles do Jogador, conforme o modo."""
        configurar = self.ctrl.fase(chat.id) == FASE_CONFIGURAR
        linhas = ap.resumo_sessao(chat, configurar)
        self.lbl_sessao.setText("\n".join(linhas))
        self.lbl_sessao.setVisible(bool(linhas))
        self.btn_config.setVisible(configurar)

        jogando = chat.modo == MODO_JOGADOR and not configurar
        self.controles_jogador.setVisible(jogando)
        if jogando:
            # Ao preencher os controles, o sinal de troca de perfil não pode agir como se fosse o usuário.
            self._atualizando_painel = True
            self.combo_perfil.setCurrentText(chat.estado.get(ARQUETIPO, ARQUETIPOS_DISPONIVEIS[0]))
            self.edit_perfil.setText(chat.estado.get(ARQUETIPO_TEXTO, ""))
            self.edit_perfil.setEnabled(self.combo_perfil.currentText() == "Personalizado")
            self._atualizando_painel = False
        self.painel.setVisible(bool(linhas) or configurar or jogando)

    # ------------------------------------------------------------------ envio de mensagens
    def _enviar_do_teclado(self) -> None:
        """Enter na caixa de entrada: envia, mas nunca interrompe uma resposta em andamento."""
        if not self._ocupado:
            self._enviar()

    def _enviar_ou_parar(self) -> None:
        """O botão principal funciona como Enviar e, durante uma resposta, como Parar."""
        if self._ocupado:
            self._parar()
        else:
            self._enviar()

    def _enviar(self) -> None:
        """Envia o texto da caixa de entrada, se não estiver vazio."""
        texto = self.entrada.toPlainText().strip()
        if texto:
            self._enviar_texto(texto)

    def _enviar_texto(self, texto: str) -> None:
        """Manda `texto` ao controlador em uma thread e limpa a caixa (o texto volta se o turno falhar)."""
        if self._ocupado:
            return
        chat = self._chat_ou_novo()
        nome = chat.estado.get(NOME)
        self._texto_a_restaurar = texto
        self.entrada.clear()
        self._iniciar_turno(lambda: self.ctrl.enviar(chat.id, texto), ap.autor_da_ia(chat.modo, nome),
                            ap.ESTILO_ASSISTENTE, abrir_config_ao_fim=True)

    def _parar(self) -> None:
        """Pede à thread atual que interrompa a resposta; o botão mostra "Parando…" até ela terminar."""
        if self._thread_atual is not None:
            self._thread_atual.parar()
            self.btn_enviar.setEnabled(False)
            self.btn_enviar.setText("Parando…")

    def _iniciar_turno(self, acao: Callable[[], Turno], autor: str, estilo: str, abrir_config_ao_fim: bool = False) -> None:
        """
        Cria a TurnoThread, liga os sinais dela aos métodos da janela e a inicia.
        `autor` e `estilo` descrevem a bolha onde a resposta vai aparecendo.
        `abrir_config_ao_fim`: se, ao terminar, o chat ficou na fase de configuração (o usuário acabou de
        escolher Mestre ou Jogador), abre o diálogo de configuração.
        """
        self._autor_stream, self._estilo_stream = autor, estilo
        self._abrir_config_ao_fim = abrir_config_ao_fim
        self._definir_ocupado(True)

        thread = TurnoThread(acao, self)
        thread.salvas.connect(self._ao_salvar)
        thread.pedaco.connect(self._ao_pedaco)
        thread.concluido.connect(self._ao_concluir)
        thread.falhou.connect(self._ao_falhar)
        thread.cancelado.connect(self._ao_cancelar)
        thread.finished.connect(lambda t=thread: self._thread_terminou(t))
        self._threads.append(thread)
        self._thread_atual = thread
        thread.start()

    def _thread_terminou(self, thread: TurnoThread) -> None:
        """A thread acabou de verdade: deixa de guardá-la e libera o objeto."""
        if thread in self._threads:
            self._threads.remove(thread)
        thread.deleteLater()

    def _definir_ocupado(self, ocupado: bool) -> None:
        """Liga ou desliga o modo "ocupado": troca o texto do botão e trava a lista, o novo chat e o painel."""
        self._ocupado = ocupado
        if not ocupado:
            self._thread_atual = None
            self._pendentes = []  # o turno acabou: nada mais ficou sem resposta
        self.btn_enviar.setEnabled(True)
        self.btn_enviar.setText("⏹  Parar" if ocupado else "Enviar")
        for controle in (self.lista, self.btn_novo, self.painel):
            controle.setEnabled(not ocupado)

    def _ao_salvar(self, salvas: list, precisa_modelo: bool) -> None:
        """O controlador já gravou estas mensagens: mostra-as e, se o modelo vai responder, abre a bolha da resposta."""
        if self._encerrando:
            return
        chat = self.chats.chat_atual
        modo = chat.modo if chat else None
        nome = chat.estado.get(NOME) if chat else None
        for mensagem in salvas:
            self.area.adicionar(ap.descrever_mensagem(mensagem, modo, nome))
        if precisa_modelo:
            # Guarda estas mensagens: se o app for fechado antes da resposta, elas são desfeitas (veja closeEvent).
            self._pendentes = list(salvas)
            self._bolha_stream = self.area.adicionar(ap.Bolha(self._estilo_stream, self._autor_stream, "…"))
        self.area.rolar_para_o_fim()

    def _ao_pedaco(self, texto: str) -> None:
        """Chegou mais texto da resposta: atualiza a bolha, com um cursor (▌) enquanto a resposta não termina."""
        if self._encerrando:
            return
        if self._bolha_stream is not None:
            self._bolha_stream.definir_texto(f"{texto} ▌" if texto else "…")
            self.area.rolar_para_o_fim()

    def _ao_concluir(self, _resposta) -> None:
        """O turno terminou bem: libera a tela, redesenha o chat e abre a configuração, se for o caso."""
        if self._encerrando:
            return
        abrir_config = self._abrir_config_ao_fim
        self._definir_ocupado(False)
        self._texto_a_restaurar = ""
        self._renderizar_chat()
        chat = self.chats.chat_atual
        if abrir_config and chat is not None and self.ctrl.fase(chat.id) == FASE_CONFIGURAR:
            self._configurar()  # o usuário acabou de escolher Mestre ou Jogador

    def _ao_falhar(self, mensagem: str) -> None:
        """O turno falhou: mostra o erro no chat e devolve o texto à caixa de entrada, para não se perder."""
        if self._encerrando:
            return
        self._definir_ocupado(False)
        texto, self._texto_a_restaurar = self._texto_a_restaurar, ""
        self._renderizar_chat(erro=mensagem)
        if texto:
            self.entrada.setPlainText(texto)  # a mensagem não se perde

    def _ao_cancelar(self) -> None:
        """O usuário apertou Parar: mostra o aviso e devolve o texto à caixa de entrada."""
        if self._encerrando:
            return
        self._definir_ocupado(False)
        texto, self._texto_a_restaurar = self._texto_a_restaurar, ""
        self._renderizar_chat(erro="Resposta interrompida.")
        if texto:
            self.entrada.setPlainText(texto)

    # ------------------------------------------------------------------ configuração, perfil e feedback
    def _configurar(self) -> None:
        """Abre o diálogo de configuração do chat atual (aventura do Mestre ou personagem do Jogador)."""
        chat = self.chats.chat_atual
        if self._ocupado or chat is None or self.ctrl.fase(chat.id) != FASE_CONFIGURAR:
            return
        if chat.modo == MODO_MESTRE:
            dialogo = DialogoMestre(self)
            if not dialogo.exec():
                return
            cenario, ficha = dialogo.valores()
            self._texto_a_restaurar = ""
            self._iniciar_turno(lambda: self.ctrl.configurar_mestre(chat.id, cenario, ficha), "🗺️ Mestre", ap.ESTILO_ASSISTENTE)
        elif chat.modo == MODO_JOGADOR:
            dialogo = DialogoJogador(self)
            if not dialogo.exec():
                return
            nome, ficha, perfil, texto_perfil = dialogo.valores()
            try:
                # A saudação do jogador não usa o modelo, então não precisa de thread.
                self.ctrl.configurar_jogador(chat.id, nome, ficha, perfil, texto_perfil)
            except ValueError as e:
                QMessageBox.warning(self, "Novo personagem", str(e))
                return
            self._renderizar_chat()

    def _ao_trocar_perfil(self) -> None:
        """O usuário mudou o perfil do jogador no painel: grava a troca e registra um aviso no chat."""
        chat = self.chats.chat_atual
        if self._atualizando_painel or self._ocupado or chat is None or chat.modo != MODO_JOGADOR:
            return
        perfil = self.combo_perfil.currentText()
        self.edit_perfil.setEnabled(perfil == "Personalizado")
        if perfil == chat.estado.get(ARQUETIPO) and self.edit_perfil.text() == chat.estado.get(ARQUETIPO_TEXTO, ""):
            return  # nada mudou (por exemplo, o campo perdeu o foco sem ser editado)
        try:
            self.ctrl.trocar_arquetipo(chat.id, perfil, self.edit_perfil.text().strip())
        except ValueError as e:
            QMessageBox.warning(self, "Perfil de jogador", str(e))
            return
        self._renderizar_chat()

    def _pedir_feedback(self) -> None:
        """Botão "Gerar feedback": a IA sai do personagem e analisa a condução do Mestre."""
        chat = self.chats.chat_atual
        if self._ocupado or chat is None:
            return
        self._texto_a_restaurar = ""
        self._iniciar_turno(lambda: self.ctrl.feedback(chat.id), "📝 Mentor", ap.ESTILO_FEEDBACK)

    # ------------------------------------------------------------------ Ollama e encerramento
    def _iniciar_ollama(self) -> None:
        """Garante, em segundo plano, que o servidor do Ollama esteja no ar."""
        self._ollama_thread = OllamaThread(self)
        self._ollama_thread.pronto.connect(self._ao_ollama_pronto)
        self._ollama_thread.start()

    def _ao_ollama_pronto(self, ativo: bool) -> None:
        """Atualiza a barra de status com o resultado da verificação do Ollama."""
        if ativo:
            self.statusBar().showMessage(f"Ollama pronto  ·  modelo local: {config.settings.ollama_model}  ·  funciona sem internet")
        else:
            self.statusBar().showMessage("O Ollama não está rodando. Inicie-o com: ollama serve")

    def _confirmar_fechar(self) -> bool:
        """Pergunta se o usuário quer mesmo fechar o app enquanto a IA ainda está respondendo."""
        resposta = QMessageBox.question(
            self, "Fechar o app",
            "A IA ainda está respondendo. Se você fechar agora, a resposta será interrompida e a sua última "
            "mensagem não será salva.\n\nFechar mesmo assim?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        return resposta == QMessageBox.StandardButton.Yes

    def _descartar_pendentes(self) -> None:
        """
        Desfaz as mensagens salvas do turno em andamento (a pergunta do usuário que ficou sem resposta).
        Normalmente é o próprio controlador que faz isso, quando a thread termina; aqui é o plano B para
        quando a thread precisa ser encerrada à força. Se a mensagem já foi desfeita, o erro é ignorado.
        """
        for mensagem in self._pendentes:
            try:
                self.chats.descartar(mensagem)
            except Exception:
                logger.debug("A mensagem %s já não estava no banco ao fechar o app.", mensagem.id)
        self._pendentes = []

    def _encerrar_threads(self) -> None:
        """
        Para as threads antes de o banco ser fechado.
        1. Pede que o turno pare e espera até ESPERA_TURNO_MS. É o caminho normal: a resposta chega em
           streaming, então a thread vê o pedido no próximo pedaço de texto, o controlador desfaz a
           pergunta sozinho e a thread termina.
        2. Se a thread continua presa, é porque o modelo ainda não devolveu o primeiro pedaço de texto
           (por exemplo, está carregando ou lendo o prompt) e não há como interromper a espera. Nesse caso,
           desfaz a pergunta pendente e só então encerra a thread à força. A ordem importa: o desfazer usa
           o banco, e a thread presa está esperando o modelo, sem usar o banco.   # ← mudou
        3. A thread do Ollama não guarda nada, então, se passar do prazo, é encerrada sem mais cuidados.
        """
        pendentes_descartados = False
        for thread in list(self._threads):
            thread.parar()
            if thread.wait(ESPERA_TURNO_MS):
                continue  # terminou sozinha
            logger.warning("O turno não terminou em %d ms; encerrando a thread à força.", ESPERA_TURNO_MS)
            if not pendentes_descartados:
                self._descartar_pendentes()
                pendentes_descartados = True
            thread.terminate()  # último recurso, aceitável porque o app está fechando
            thread.wait(ESPERA_APOS_TERMINAR_MS)

        if self._ollama_thread is not None and not self._ollama_thread.wait(ESPERA_OLLAMA_MS):
            self._ollama_thread.terminate()
            self._ollama_thread.wait(ESPERA_APOS_TERMINAR_MS)

    def closeEvent(self, evento) -> None:
        """
        Fecha o app com segurança. Se a IA está respondendo, pergunta antes; "Não" cancela o fechamento.
        Depois encerra as threads (veja `_encerrar_threads`) e só então fecha o banco, porque uma thread
        ainda rodando poderia gravar nele.
        """
        if any(thread.isRunning() for thread in self._threads) and not self._confirmar_fechar():
            evento.ignore()  # o usuário desistiu de fechar
            return
        self._encerrando = True  # respostas que chegarem depois de fechar o banco são ignoradas
        self._encerrar_threads()
        self.chats.fechar()
        super().closeEvent(evento)