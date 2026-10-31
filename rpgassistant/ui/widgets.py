"""Widgets da janela: bolha de mensagem, área de conversa e caixa de entrada."""

from __future__ import annotations

from typing import List

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QScrollArea, QVBoxLayout, QWidget

from rpgassistant.ui.apresentacao import (
    ESTILO_ASSISTENTE, ESTILO_FEEDBACK, ESTILO_RECUSA, ESTILO_USUARIO, Bolha, markdown_para_exibir,
)


class BolhaMensagem(QFrame):
    """Uma mensagem: autor, texto em Markdown e um rodapé pequeno (fontes, métricas, estado de combate)."""

    def __init__(self, bolha: Bolha, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setObjectName("bolha")
        self.setProperty("estilo", bolha.estilo)  # o tema escolhe a cor por este valor

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        self._autor = QLabel(bolha.autor)
        self._autor.setObjectName("autor")
        self._texto = QLabel()
        self._texto.setObjectName("texto")
        self._texto.setTextFormat(Qt.TextFormat.MarkdownText)
        self._texto.setWordWrap(True)
        self._texto.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._rodape = QLabel(bolha.rodape)
        self._rodape.setObjectName("rodape")
        self._rodape.setWordWrap(True)
        self._rodape.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        layout.addWidget(self._autor)
        layout.addWidget(self._texto)
        layout.addWidget(self._rodape)

        self._autor.setVisible(bool(bolha.autor))
        self._rodape.setVisible(bool(bolha.rodape))
        self.definir_texto(bolha.texto)

    def definir_texto(self, texto: str) -> None:
        self._texto.setText(markdown_para_exibir(texto))


class AreaConversa(QScrollArea):
    """Lista rolável de bolhas. Mensagens do usuário ficam à direita, as da IA à esquerda e os avisos ocupam a largura toda."""

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        conteudo = QWidget()
        self._layout = QVBoxLayout(conteudo)
        self._layout.setContentsMargins(16, 12, 16, 12)
        self._layout.setSpacing(10)
        self._layout.addStretch(1)  # empurra as bolhas para o topo
        self.setWidget(conteudo)
        self._linhas: List[QWidget] = []
        self._bolhas: List[BolhaMensagem] = []

    @property
    def quantidade(self) -> int:
        return len(self._linhas)

    @property
    def bolhas(self) -> List[BolhaMensagem]:
        return list(self._bolhas)

    def limpar(self) -> None:
        for linha in self._linhas:
            self._layout.removeWidget(linha)
            linha.deleteLater()
        self._linhas = []
        self._bolhas = []

    def adicionar(self, bolha: Bolha) -> BolhaMensagem:
        widget = BolhaMensagem(bolha)
        linha = QWidget()
        disposicao = QHBoxLayout(linha)
        disposicao.setContentsMargins(0, 0, 0, 0)
        if bolha.estilo == ESTILO_USUARIO:
            disposicao.addStretch(1)
            disposicao.addWidget(widget, 4)
        elif bolha.estilo in (ESTILO_ASSISTENTE, ESTILO_RECUSA, ESTILO_FEEDBACK):
            disposicao.addWidget(widget, 4)
            disposicao.addStretch(1)
        else:
            disposicao.addWidget(widget)
        self._layout.insertWidget(self._layout.count() - 1, linha)  # antes do espaço flexível do final
        self._linhas.append(linha)
        self._bolhas.append(widget)
        return widget

    def rolar_para_o_fim(self) -> None:
        # adiado para depois de o Qt recalcular o tamanho das bolhas novas
        QTimer.singleShot(0, lambda: self.verticalScrollBar().setValue(self.verticalScrollBar().maximum()))


class CaixaDeEntrada(QPlainTextEdit):
    """Caixa de texto em que Enter envia e Shift+Enter quebra a linha."""

    enviar = Signal()

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setPlaceholderText("Escreva aqui (Enter envia, Shift+Enter quebra a linha)")
        self.setMaximumHeight(110)

    def keyPressEvent(self, evento) -> None:
        if evento.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
            evento.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self.enviar.emit()
            return
        super().keyPressEvent(evento)