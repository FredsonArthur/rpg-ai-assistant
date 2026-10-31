"""
RPG AI Assistant: ponto de entrada.

Uso:  python main.py
"""

import sys


def main() -> int:
    from rpgassistant import config
    from rpgassistant.logs import configurar_logs

    configurar_logs()
    config.settings.garantir_pastas()

    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
    except ImportError:
        print("O PySide6 não está instalado. Rode:  pip install -r requirements.txt")
        return 1

    from rpgassistant.core.chats import GerenciadorDeChats
    from rpgassistant.core.controller import ControladorDeChat
    from rpgassistant.errors import BancoDeDadosError
    from rpgassistant.ui.janela import JanelaPrincipal

    app = QApplication(sys.argv)
    app.setApplicationName("RPG AI Assistant")

    try:
        gerenciador = GerenciadorDeChats.abrir()
    except BancoDeDadosError as e:
        QMessageBox.critical(None, "Banco de chats", str(e))
        return 1

    janela = JanelaPrincipal(ControladorDeChat(gerenciador))
    janela.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())