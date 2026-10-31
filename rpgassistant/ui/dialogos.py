"""Janelas de configuração: nova aventura (Mestre) e novo personagem (Jogador)."""

from __future__ import annotations

from typing import Tuple

from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QWidget

from rpgassistant.modes import jogador, mestre


class DialogoMestre(QDialog):
    """Cenário e ficha do jogador para uma nova aventura."""

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nova aventura solo")
        self.setMinimumWidth(520)

        self.cenario = QComboBox()
        self.cenario.addItems(mestre.CENARIOS)
        self.cenario_livre = QLineEdit()
        self.cenario_livre.setPlaceholderText("Opcional: descreva o seu próprio cenário")
        self.ficha = QLineEdit(mestre.FICHA_PADRAO)

        formulario = QFormLayout(self)
        formulario.addRow("Cenário:", self.cenario)
        formulario.addRow("Ou escreva um:", self.cenario_livre)
        formulario.addRow("Sua ficha:", self.ficha)
        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        formulario.addRow(botoes)

    def valores(self) -> Tuple[str, str]:
        """(cenário, ficha). O cenário escrito à mão vale mais que o da lista."""
        return (self.cenario_livre.text().strip() or self.cenario.currentText(), self.ficha.text().strip())


class DialogoJogador(QDialog):
    """Personagem que a IA vai interpretar e o perfil de jogador."""

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Novo personagem da IA")
        self.setMinimumWidth(520)

        self.nome = QLineEdit("Lia")
        self.ficha = QLineEdit(jogador.FICHA_PADRAO)
        self.perfil = QComboBox()
        self.perfil.addItems(jogador.ARQUETIPOS_DISPONIVEIS)
        self.perfil_texto = QLineEdit()
        self.perfil_texto.setPlaceholderText("Só para o perfil Personalizado (ex.: desconfiado e cauteloso)")
        self.perfil_texto.setEnabled(False)
        self.perfil.currentTextChanged.connect(lambda texto: self.perfil_texto.setEnabled(texto == "Personalizado"))

        formulario = QFormLayout(self)
        formulario.addRow("Nome:", self.nome)
        formulario.addRow("Ficha e personalidade:", self.ficha)
        formulario.addRow("Perfil de jogador:", self.perfil)
        formulario.addRow("Descreva o perfil:", self.perfil_texto)
        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        formulario.addRow(botoes)

    def valores(self) -> Tuple[str, str, str, str]:
        """(nome, ficha, perfil, texto do perfil personalizado)."""
        return (self.nome.text().strip(), self.ficha.text().strip(), self.perfil.currentText(),
                self.perfil_texto.text().strip())