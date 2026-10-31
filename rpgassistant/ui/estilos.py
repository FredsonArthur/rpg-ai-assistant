"""Tema escuro da janela (QSS, o CSS do Qt)."""

TEMA_ESCURO = """
QWidget { background-color: #16181d; color: #e6e8ee; font-size: 14px; }
QMainWindow, QSplitter { background-color: #16181d; }
QSplitter::handle { background-color: #23262e; width: 1px; }

QLabel#secao { color: #8b93a7; font-size: 12px; font-weight: bold; padding: 6px 4px 2px 4px; }
QLabel#titulo { font-size: 18px; font-weight: bold; }
QLabel#selo { background-color: #262b38; color: #aab4d4; border-radius: 10px; padding: 3px 10px; font-size: 12px; }

QListWidget { background-color: #1b1e25; border: none; outline: none; }
QListWidget::item { padding: 9px 8px; border-radius: 6px; margin: 1px 4px; }
QListWidget::item:selected { background-color: #2b3350; color: #ffffff; }
QListWidget::item:hover:!selected { background-color: #22262f; }

QPushButton { background-color: #2b3350; border: none; border-radius: 6px; padding: 8px 14px; }
QPushButton:hover { background-color: #36406a; }
QPushButton:disabled { background-color: #22252d; color: #6b7080; }
QPushButton#novo { background-color: #3b5bdb; font-weight: bold; margin: 4px; }
QPushButton#novo:hover { background-color: #4c6ef5; }
QPushButton#enviar { background-color: #3b5bdb; font-weight: bold; padding: 10px 18px; }
QPushButton#enviar:hover { background-color: #4c6ef5; }

QFrame#painel { background-color: #1b1e25; border-radius: 8px; }
QPlainTextEdit, QLineEdit, QComboBox {
    background-color: #1f232c; border: 1px solid #2c313d; border-radius: 6px; padding: 6px;
    selection-background-color: #3b5bdb;
}
QPlainTextEdit:focus, QLineEdit:focus { border: 1px solid #4c6ef5; }
QComboBox QAbstractItemView { background-color: #1f232c; selection-background-color: #2b3350; }

QScrollArea { border: none; }
QScrollBar:vertical { background: #16181d; width: 10px; }
QScrollBar::handle:vertical { background: #2f3441; border-radius: 5px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QFrame#bolha { border-radius: 12px; }
QFrame#bolha[estilo="usuario"] { background-color: #2f4bb0; }
QFrame#bolha[estilo="assistente"] { background-color: #232733; }
QFrame#bolha[estilo="aviso"] { background-color: #1d2029; border: 1px dashed #343a4a; }
QFrame#bolha[estilo="ajuda"] { background-color: #1d2a3a; border: 1px solid #2f4a6b; }
QFrame#bolha[estilo="feedback"] { background-color: #2a2540; border: 1px solid #5a4aa8; }
QFrame#bolha[estilo="recusa"] { background-color: #30262a; border: 1px solid #6b3a47; }
QFrame#bolha[estilo="erro"] { background-color: #3a2020; border: 1px solid #a33a3a; }
QLabel#autor { color: #9fb0ff; font-weight: bold; font-size: 12px; background: transparent; }
QLabel#texto { background: transparent; }
QLabel#rodape { color: #8b93a7; font-size: 11px; background: transparent; }

QMenu { background-color: #1f232c; border: 1px solid #2c313d; }
QMenu::item { padding: 6px 18px; }
QMenu::item:selected { background-color: #2b3350; }
QStatusBar { background-color: #12141a; color: #8b93a7; }
"""