"""
RPG AI Assistant: ponto de entrada.

Uso:  python main.py
Se algo der errado na instalação:  python -m rpgassistant.diagnostico
"""

import sys


def main() -> int:
    from rpgassistant import ambiente, config
    from rpgassistant.logs import configurar_logs

    configurar_logs()

    # Confere o Python e as bibliotecas antes de abrir qualquer coisa, com mensagens que dizem o que fazer.
    problemas = ambiente.verificar_ambiente()
    for problema in problemas:
        print(("ERRO: " if problema.gravidade == "erro" else "AVISO: ") + problema.texto, file=sys.stderr)
    if any(p.gravidade == "erro" for p in problemas):
        print("\nPara ver o estado completo da instalação:  python -m rpgassistant.diagnostico", file=sys.stderr)
        return 1

    config.settings.garantir_pastas()

    from PySide6.QtWidgets import QApplication, QMessageBox

    from rpgassistant.core.chats import GerenciadorDeChats
    from rpgassistant.core.controller import ControladorDeChat
    from rpgassistant.errors import BancoDeDadosError
    from rpgassistant.ui.janela import JanelaPrincipal

    app = QApplication(sys.argv)
    app.setApplicationName("RPG AI Assistant")

    try:
        gerenciador = GerenciadorDeChats.abrir()
    except BancoDeDadosError as e:
        print(f"ERRO: {e}", file=sys.stderr)
        QMessageBox.critical(None, "Banco de chats", str(e))
        return 1

    janela = JanelaPrincipal(ControladorDeChat(gerenciador))
    janela.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())