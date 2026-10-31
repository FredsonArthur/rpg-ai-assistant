"""
Qt falso, só para testes
------------------------
Imita o PySide6 com classes simples e "estritas": só existem os métodos que a interface realmente usa
(um nome errado vira AttributeError). Assim dá para exercitar toda a lógica da janela, sem tela e sem
instalar o Qt. As threads rodam de forma síncrona: `start()` executa `run()` na hora.

Isto NÃO testa a aparência nem o comportamento do Qt de verdade; para isso, use tests/test_ui_qt.py.
"""

import sys
import types
from typing import Any, Callable, Dict, List, Optional

_PREFIXOS = ("PySide6", "rpgassistant.ui")
_guardados: Dict[str, Any] = {}


class _Sinal:
    def __init__(self) -> None:
        self._ligados: List[Callable] = []

    def connect(self, funcao: Callable) -> None:
        self._ligados.append(funcao)

    def emit(self, *args: Any) -> None:
        for funcao in list(self._ligados):
            funcao(*args)


class Signal:
    """Descritor: cada objeto ganha o seu próprio sinal."""

    def __init__(self, *tipos: Any) -> None:
        self.nome = ""

    def __set_name__(self, dono: type, nome: str) -> None:
        self.nome = nome

    def __get__(self, objeto: Any, dono: type = None) -> Any:
        if objeto is None:
            return self
        return objeto.__dict__.setdefault("_sinal_" + self.nome, _Sinal())


class _Obj:
    _NOOPS: frozenset = frozenset()

    def __getattr__(self, nome: str) -> Any:
        for classe in type(self).__mro__:
            if nome in classe.__dict__.get("_NOOPS", ()):
                return lambda *a, **k: None
        raise AttributeError(f"{type(self).__name__} (Qt falso) não tem {nome!r}")


class _Enum:
    pass


def _enum(**valores: int) -> type:
    return type("Enum", (_Enum,), valores)


# ----------------------------------------------------------------------------- QtCore
class Qt:
    TextFormat = _enum(MarkdownText=1)
    TextInteractionFlag = _enum(TextSelectableByMouse=1)
    ScrollBarPolicy = _enum(ScrollBarAlwaysOff=1)
    Orientation = _enum(Horizontal=1)
    ItemDataRole = _enum(UserRole=256)
    ContextMenuPolicy = _enum(CustomContextMenu=1)
    Key = _enum(Key_Return=16777220, Key_Enter=16777221, Key_A=65)
    KeyboardModifier = _enum(ShiftModifier=2, NoModifier=0)


class QTimer:
    @staticmethod
    def singleShot(_ms: int, funcao: Callable) -> None:
        funcao()


class QObject(_Obj):
    _NOOPS = frozenset({"deleteLater"})

    def __init__(self, parent: Any = None) -> None:
        self._bloqueado = False

    def blockSignals(self, bloquear: bool) -> bool:
        antes, self._bloqueado = self._bloqueado, bloquear
        return antes


class QThread(QObject):
    finished = Signal()

    def start(self) -> None:
        self.run()
        self.finished.emit()

    def wait(self, _ms: int = 0) -> bool:
        return True

    def isRunning(self) -> bool:
        return False


# ----------------------------------------------------------------------------- QtGui
class QKeySequence:
    def __init__(self, texto: str) -> None:
        self.texto = texto


class QShortcut(QObject):
    registrados: List["QShortcut"] = []
    activated = Signal()

    def __init__(self, sequencia: QKeySequence, parent: Any = None) -> None:
        super().__init__(parent)
        self.sequencia = sequencia.texto
        QShortcut.registrados.append(self)


# ----------------------------------------------------------------------------- QtWidgets
class QWidget(QObject):
    _NOOPS = frozenset({"setObjectName", "setStyleSheet", "setMinimumWidth", "setMaximumHeight", "setWindowTitle",
                        "resize", "setFocus", "show", "setContextMenuPolicy", "setFrameShape", "setSizes"})

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._ativo = True
        self._visivel = True
        self._propriedades: Dict[str, Any] = {}
        self.apagado = False

    def setEnabled(self, ativo: bool) -> None:
        self._ativo = bool(ativo)

    def isEnabled(self) -> bool:
        return self._ativo

    def setVisible(self, visivel: bool) -> None:
        self._visivel = bool(visivel)

    def isVisible(self) -> bool:
        return self._visivel

    def setProperty(self, nome: str, valor: Any) -> None:
        self._propriedades[nome] = valor

    def property(self, nome: str) -> Any:
        return self._propriedades.get(nome)

    def deleteLater(self) -> None:
        self.apagado = True

    def mapToGlobal(self, posicao: Any) -> Any:
        return posicao


class QFrame(QWidget):
    Shape = _enum(NoFrame=0)


class QLabel(QWidget):
    def __init__(self, texto: str = "", parent: Any = None) -> None:
        super().__init__(parent)
        self._texto = texto

    def setText(self, texto: str) -> None:
        self._texto = texto

    def text(self) -> str:
        return self._texto

    _NOOPS = frozenset({"setWordWrap", "setTextFormat", "setTextInteractionFlags", "setOpenExternalLinks"})


class QPushButton(QWidget):
    clicked = Signal()

    def __init__(self, texto: str = "", parent: Any = None) -> None:
        super().__init__(parent)
        self._texto = texto

    def setText(self, texto: str) -> None:
        self._texto = texto

    def text(self) -> str:
        return self._texto


class QListWidgetItem:
    def __init__(self, texto: str = "") -> None:
        self._texto = texto
        self._dados: Dict[int, Any] = {}

    def text(self) -> str:
        return self._texto

    def setData(self, papel: int, valor: Any) -> None:
        self._dados[papel] = valor

    def data(self, papel: int) -> Any:
        return self._dados.get(papel)


class QListWidget(QWidget):
    currentRowChanged = Signal()
    customContextMenuRequested = Signal()

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._itens: List[QListWidgetItem] = []
        self._linha = -1

    def clear(self) -> None:
        self._itens, self._linha = [], -1

    def addItem(self, item: QListWidgetItem) -> None:
        self._itens.append(item)

    def count(self) -> int:
        return len(self._itens)

    def item(self, linha: int) -> Optional[QListWidgetItem]:
        return self._itens[linha] if 0 <= linha < len(self._itens) else None

    def itemAt(self, posicao: Any) -> Optional[QListWidgetItem]:
        return self.item(posicao) if isinstance(posicao, int) else None

    def currentRow(self) -> int:
        return self._linha

    def setCurrentRow(self, linha: int) -> None:
        mudou = linha != self._linha
        self._linha = linha
        if mudou and not self._bloqueado:
            self.currentRowChanged.emit(linha)

    def setCurrentItem(self, item: QListWidgetItem) -> None:
        self.setCurrentRow(self._itens.index(item))


class QSplitter(QWidget):
    _NOOPS = frozenset({"setChildrenCollapsible", "setStretchFactor", "setSizes"})

    def __init__(self, orientacao: Any = None, parent: Any = None) -> None:
        super().__init__(parent)
        self.filhos: List[Any] = []

    def addWidget(self, widget: Any) -> None:
        self.filhos.append(widget)


class _BarraDeRolagem:
    def __init__(self) -> None:
        self.valor, self._maximo = 0, 100

    def setValue(self, valor: int) -> None:
        self.valor = valor

    def maximum(self) -> int:
        return self._maximo


class QScrollArea(QFrame):
    _NOOPS = frozenset({"setWidgetResizable", "setHorizontalScrollBarPolicy"})

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._barra = _BarraDeRolagem()

    def setWidget(self, widget: Any) -> None:
        self.conteudo = widget

    def verticalScrollBar(self) -> _BarraDeRolagem:
        return self._barra


class QPlainTextEdit(QWidget):
    _NOOPS = frozenset({"setPlaceholderText"})

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._texto = ""

    def toPlainText(self) -> str:
        return self._texto

    def setPlainText(self, texto: str) -> None:
        self._texto = texto

    def clear(self) -> None:
        self._texto = ""

    def keyPressEvent(self, evento: Any) -> None:
        self._texto += getattr(evento, "texto", "")


class QLineEdit(QWidget):
    EchoMode = _enum(Normal=0)
    editingFinished = Signal()
    _NOOPS = frozenset({"setPlaceholderText"})

    def __init__(self, texto: str = "", parent: Any = None) -> None:
        super().__init__(parent)
        self._texto = texto

    def text(self) -> str:
        return self._texto

    def setText(self, texto: str) -> None:
        self._texto = texto


class QComboBox(QWidget):
    currentTextChanged = Signal()

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._itens: List[str] = []
        self._atual = ""

    def addItems(self, textos: List[str]) -> None:
        self._itens.extend(textos)
        if not self._atual and self._itens:
            self._atual = self._itens[0]

    def currentText(self) -> str:
        return self._atual

    def setCurrentText(self, texto: str) -> None:
        mudou = texto != self._atual
        self._atual = texto
        if mudou and not self._bloqueado:
            self.currentTextChanged.emit(texto)


class QDialog(QWidget):
    resultado = 1  # o que exec() devolve; os testes mudam para simular "Cancelar"

    def exec(self) -> int:
        return QDialog.resultado

    def accept(self) -> None:
        pass

    def reject(self) -> None:
        pass


class QDialogButtonBox(QWidget):
    StandardButton = _enum(Ok=1, Cancel=2)
    accepted = Signal()
    rejected = Signal()

    def __init__(self, botoes: int = 0, parent: Any = None) -> None:
        super().__init__(parent)


class _Layout(_Obj):
    _NOOPS = frozenset({"setContentsMargins", "setSpacing"})

    def __init__(self, pai: Any = None) -> None:
        self.itens: List[Any] = []

    def addWidget(self, widget: Any, stretch: int = 0) -> None:
        self.itens.append(widget)

    def addLayout(self, layout: Any) -> None:
        self.itens.append(layout)

    def addStretch(self, stretch: int = 0) -> None:
        self.itens.append(None)  # o Qt também conta o espaço flexível como um item

    def insertWidget(self, indice: int, widget: Any, stretch: int = 0) -> None:
        self.itens.insert(indice, widget)

    def count(self) -> int:
        return len(self.itens)

    def removeWidget(self, widget: Any) -> None:
        self.itens.remove(widget)


class QVBoxLayout(_Layout):
    pass


class QHBoxLayout(_Layout):
    pass


class QFormLayout(_Layout):
    def addRow(self, *args: Any) -> None:
        self.itens.append(args)


class QMainWindow(QWidget):
    class _BarraDeStatus:
        def __init__(self) -> None:
            self.mensagem = ""

        def showMessage(self, texto: str) -> None:
            self.mensagem = texto

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._status = QMainWindow._BarraDeStatus()
        self.fechada = False

    def setCentralWidget(self, widget: Any) -> None:
        self.central = widget

    def statusBar(self) -> "QMainWindow._BarraDeStatus":
        return self._status

    def closeEvent(self, evento: Any) -> None:
        self.fechada = True

    def close(self) -> None:
        self.closeEvent(object())


class _Acao:
    def __init__(self, texto: str) -> None:
        self.texto = texto


class QMenu(QWidget):
    escolher: Optional[str] = None  # texto da ação que o "usuário" escolhe

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.acoes: List[_Acao] = []

    def addAction(self, texto: str) -> _Acao:
        acao = _Acao(texto)
        self.acoes.append(acao)
        return acao

    def exec(self, posicao: Any = None) -> Optional[_Acao]:
        return next((a for a in self.acoes if QMenu.escolher and a.texto.startswith(QMenu.escolher)), None)


class QMessageBox:
    StandardButton = _enum(Yes=16384, No=65536)
    resposta = StandardButton.Yes
    chamadas: List[tuple] = []

    @staticmethod
    def warning(parent: Any, titulo: str, texto: str) -> None:
        QMessageBox.chamadas.append(("warning", titulo, texto))

    @staticmethod
    def critical(parent: Any, titulo: str, texto: str) -> None:
        QMessageBox.chamadas.append(("critical", titulo, texto))

    @staticmethod
    def question(parent: Any, titulo: str, texto: str, botoes: int = 0, padrao: int = 0) -> int:
        QMessageBox.chamadas.append(("question", titulo, texto))
        return QMessageBox.resposta


class QInputDialog:
    retorno = ("", False)

    @staticmethod
    def getText(parent: Any, titulo: str, rotulo: str, modo: Any = None, texto: str = "") -> tuple:
        return QInputDialog.retorno


class QApplication(QObject):
    pass


# ----------------------------------------------------------------------------- instalação
def _modulo(nome: str, **atributos: Any) -> types.ModuleType:
    modulo = types.ModuleType(nome)
    for chave, valor in atributos.items():
        setattr(modulo, chave, valor)
    return modulo


def instalar() -> None:
    """Coloca o Qt falso no lugar do PySide6 e esquece os módulos da interface já importados."""
    for nome in list(sys.modules):
        if nome.startswith(_PREFIXOS):
            _guardados[nome] = sys.modules.pop(nome)

    widgets = {n: v for n, v in globals().items() if n.startswith("Q") and n not in ("QObject", "QThread", "QTimer", "QKeySequence", "QShortcut")}
    sys.modules["PySide6"] = _modulo("PySide6")
    sys.modules["PySide6.QtCore"] = _modulo("PySide6.QtCore", Qt=Qt, QTimer=QTimer, QThread=QThread, QObject=QObject, Signal=Signal)
    sys.modules["PySide6.QtGui"] = _modulo("PySide6.QtGui", QKeySequence=QKeySequence, QShortcut=QShortcut)
    sys.modules["PySide6.QtWidgets"] = _modulo("PySide6.QtWidgets", **widgets)
    QShortcut.registrados.clear()
    QMessageBox.chamadas.clear()
    QDialog.resultado = 1
    QMessageBox.resposta = QMessageBox.StandardButton.Yes
    QInputDialog.retorno = ("", False)
    QMenu.escolher = None


def remover() -> None:
    """Tira o Qt falso e devolve os módulos que estavam carregados antes (por exemplo, o PySide6 de verdade)."""
    for nome in list(sys.modules):
        if nome.startswith(_PREFIXOS):
            del sys.modules[nome]
    sys.modules.update(_guardados)
    _guardados.clear()