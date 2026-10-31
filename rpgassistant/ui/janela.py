"""
Janela principal
----------------
Lista de chats à esquerda e a conversa à direita. Toda a lógica (modo, histórico, respostas, salvamento)
está no ControladorDeChat; esta janela só mostra o que ele devolve e roda o modelo fora da thread da tela.
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
from rpgassistant.core.models import Chat
from rpgassistant.core.modos import MODO_JOGADOR, MODO_MESTRE
from rpgassistant.errors import ChatNaoEncontrado
from rpgassistant.modes.jogador import ARQUETIPOS_DISPONIVEIS
from rpgassistant.ui import apresentacao as ap
from rpgassistant.ui.dialogos import DialogoJogador, DialogoMestre
from rpgassistant.ui.estilos import TEMA_ESCURO
from rpgassistant.ui.widgets import AreaConversa, BolhaMensagem, CaixaDeEntrada
from rpgassistant.ui.workers import OllamaThread, TurnoThread

logger = logging.getLogger(__name__)


class JanelaPrincipal(QMainWindow):
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
        return self._ocupado

    def _montar_interface(self) -> None:
        divisor = QSplitter(Qt.Orientation.Horizontal)
        divisor.addWidget(self._montar_lateral())
        divisor.addWidget(self._montar_conversa())
        divisor.setChildrenCollapsible(False)
        divisor.setStretchFactor(0, 0)
        divisor.setStretchFactor(1, 1)
        divisor.setSizes([290, 830])
        self.setCentralWidget(divisor)

    def _montar_lateral(self) -> QWidget:
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
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self._novo_chat)
        QShortcut(QKeySequence("F2"), self).activated.connect(self._renomear)

    # ------------------------------------------------------------------ lista de chats
    def _abrir_chat_inicial(self) -> None:
        if self.chats.restaurar_ultimo() is None:
            self.chats.novo_chat()
        self._renderizar_chat()

    def _recarregar_lista(self) -> None:
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
        item = self.lista.item(linha) if linha >= 0 else None
        if item is None or self._ocupado:
            return
        try:
            self.chats.abrir_chat(item.data(Qt.ItemDataRole.UserRole))
        except ChatNaoEncontrado:
            pass
        self._renderizar_chat()

    def _menu_da_lista(self, posicao) -> None:
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
        if self._ocupado:
            return
        self.chats.novo_chat()
        self._renderizar_chat()
        self.entrada.setFocus()

    def _renomear(self) -> None:
        chat = self.chats.chat_atual
        if chat is None or self._ocupado:
            return
        texto, confirmou = QInputDialog.getText(self, "Renomear chat", "Novo título:", QLineEdit.EchoMode.Normal, chat.titulo)
        if not confirmou:
            return
        try:
            self.chats.renomear(chat.id, texto)
        except ValueError as e:
            QMessageBox.warning(self, "Renomear chat", str(e))
            return
        self._renderizar_chat()

    def _excluir(self) -> None:
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
        configurar = self.ctrl.fase(chat.id) == FASE_CONFIGURAR
        linhas = ap.resumo_sessao(chat, configurar)
        self.lbl_sessao.setText("\n".join(linhas))
        self.lbl_sessao.setVisible(bool(linhas))
        self.btn_config.setVisible(configurar)

        jogando = chat.modo == MODO_JOGADOR and not configurar
        self.controles_jogador.setVisible(jogando)
        if jogando:
            self._atualizando_painel = True
            self.combo_perfil.setCurrentText(chat.estado.get(ARQUETIPO, ARQUETIPOS_DISPONIVEIS[0]))
            self.edit_perfil.setText(chat.estado.get(ARQUETIPO_TEXTO, ""))
            self.edit_perfil.setEnabled(self.combo_perfil.currentText() == "Personalizado")
            self._atualizando_painel = False
        self.painel.setVisible(bool(linhas) or configurar or jogando)

    # ------------------------------------------------------------------ envio de mensagens
    def _enviar_do_teclado(self) -> None:
        if not self._ocupado:
            self._enviar()

    def _enviar_ou_parar(self) -> None:
        if self._ocupado:
            self._parar()
        else:
            self._enviar()

    def _enviar(self) -> None:
        texto = self.entrada.toPlainText().strip()
        if texto:
            self._enviar_texto(texto)

    def _enviar_texto(self, texto: str) -> None:
        if self._ocupado:
            return
        chat = self._chat_ou_novo()
        nome = chat.estado.get(NOME)
        self._texto_a_restaurar = texto
        self.entrada.clear()
        self._iniciar_turno(lambda: self.ctrl.enviar(chat.id, texto), ap.autor_da_ia(chat.modo, nome),
                            ap.ESTILO_ASSISTENTE, abrir_config_ao_fim=True)

    def _parar(self) -> None:
        if self._thread_atual is not None:
            self._thread_atual.parar()
            self.btn_enviar.setEnabled(False)
            self.btn_enviar.setText("Parando…")

    def _iniciar_turno(self, acao: Callable[[], Turno], autor: str, estilo: str, abrir_config_ao_fim: bool = False) -> None:
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
        if thread in self._threads:
            self._threads.remove(thread)
        thread.deleteLater()

    def _definir_ocupado(self, ocupado: bool) -> None:
        self._ocupado = ocupado
        if not ocupado:
            self._thread_atual = None
        self.btn_enviar.setEnabled(True)
        self.btn_enviar.setText("⏹  Parar" if ocupado else "Enviar")
        for controle in (self.lista, self.btn_novo, self.painel):
            controle.setEnabled(not ocupado)

    def _ao_salvar(self, salvas: list, precisa_modelo: bool) -> None:
        if self._encerrando:
            return
        chat = self.chats.chat_atual
        modo = chat.modo if chat else None
        nome = chat.estado.get(NOME) if chat else None
        for mensagem in salvas:
            self.area.adicionar(ap.descrever_mensagem(mensagem, modo, nome))
        if precisa_modelo:
            self._bolha_stream = self.area.adicionar(ap.Bolha(self._estilo_stream, self._autor_stream, "…"))
        self.area.rolar_para_o_fim()

    def _ao_pedaco(self, texto: str) -> None:
        if self._encerrando:
            return
        if self._bolha_stream is not None:
            self._bolha_stream.definir_texto(f"{texto} ▌" if texto else "…")
            self.area.rolar_para_o_fim()

    def _ao_concluir(self, _resposta) -> None:
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
        if self._encerrando:
            return
        self._definir_ocupado(False)
        texto, self._texto_a_restaurar = self._texto_a_restaurar, ""
        self._renderizar_chat(erro=mensagem)
        if texto:
            self.entrada.setPlainText(texto)  # a mensagem não se perde

    def _ao_cancelar(self) -> None:
        if self._encerrando:
            return
        self._definir_ocupado(False)
        texto, self._texto_a_restaurar = self._texto_a_restaurar, ""
        self._renderizar_chat(erro="Resposta interrompida.")
        if texto:
            self.entrada.setPlainText(texto)

    # ------------------------------------------------------------------ configuração, perfil e feedback
    def _configurar(self) -> None:
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
                self.ctrl.configurar_jogador(chat.id, nome, ficha, perfil, texto_perfil)
            except ValueError as e:
                QMessageBox.warning(self, "Novo personagem", str(e))
                return
            self._renderizar_chat()

    def _ao_trocar_perfil(self) -> None:
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
        chat = self.chats.chat_atual
        if self._ocupado or chat is None:
            return
        self._texto_a_restaurar = ""
        self._iniciar_turno(lambda: self.ctrl.feedback(chat.id), "📝 Mentor", ap.ESTILO_FEEDBACK)

    # ------------------------------------------------------------------ Ollama e encerramento
    def _iniciar_ollama(self) -> None:
        self._ollama_thread = OllamaThread(self)
        self._ollama_thread.pronto.connect(self._ao_ollama_pronto)
        self._ollama_thread.start()

    def _ao_ollama_pronto(self, ativo: bool) -> None:
        if ativo:
            self.statusBar().showMessage(f"Ollama pronto  ·  modelo local: {config.settings.ollama_model}  ·  funciona sem internet")
        else:
            self.statusBar().showMessage("O Ollama não está rodando. Inicie-o com: ollama serve")

    def closeEvent(self, evento) -> None:
        self._encerrando = True  # respostas que chegarem depois de fechar o banco são ignoradas
        for thread in list(self._threads):
            thread.parar()
            thread.wait(5000)
        if self._ollama_thread is not None:
            self._ollama_thread.wait(2000)
        self.chats.fechar()
        super().closeEvent(evento)