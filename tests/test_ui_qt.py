"""
Teste de fumaça com o Qt de verdade (PySide6), em modo "offscreen" (sem abrir janela na tela).
É ignorado se o PySide6 não estiver instalado. Os testes de lógica, que rodam sempre, estão em
tests/test_ui_logica.py (com um Qt falso).
"""

import importlib.util
import os
import time
import unittest

from tests.helpers import BaseTeste, OllamaFalso, RelogioFalso, modelo

TEM_PYSIDE = importlib.util.find_spec("PySide6") is not None


@unittest.skipUnless(TEM_PYSIDE, "PySide6 não está instalado")
class JanelaQtTest(BaseTeste):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        from rpgassistant.core.chats import GerenciadorDeChats
        from rpgassistant.core.controller import ControladorDeChat
        from rpgassistant.storage.database import Database
        from rpgassistant.storage.repository import RepositorioChats
        from rpgassistant.ui.janela import JanelaPrincipal

        self.usar_ollama(OllamaFalso(responder=modelo))
        self.usar_busca("CTX-LIVROS", "Core | PHB", similaridade=0.8)
        self.ger = GerenciadorDeChats(RepositorioChats(Database(":memory:"), agora=RelogioFalso()))
        self.addCleanup(self.ger.fechar)
        self.janela = JanelaPrincipal(ControladorDeChat(self.ger), iniciar_ollama=False)
        self.addCleanup(self.janela.deleteLater)

    def esperar(self, condicao, limite: float = 20.0) -> bool:
        """Deixa o Qt processar eventos (e as threads entregarem sinais) até a condição ficar verdadeira."""
        fim = time.monotonic() + limite
        while time.monotonic() < fim:
            self.app.processEvents()
            if condicao():
                return True
            time.sleep(0.01)
        return False

    def test_abre_com_as_boas_vindas(self):
        self.assertEqual(self.janela.lista.count(), 1)
        self.assertEqual(self.janela.area.quantidade, 1)
        self.assertEqual(self.janela.btn_enviar.text(), "Enviar")

    def test_pergunta_e_resposta_em_thread(self):
        self.janela.entrada.setPlainText("Como funciona a condição Agarrado?")
        self.janela.btn_enviar.click()
        self.assertTrue(self.esperar(lambda: not self.janela.ocupado and self.janela.area.quantidade >= 3),
                        "a resposta não chegou a tempo")
        self.assertEqual(self.janela.entrada.toPlainText(), "")
        self.assertIn("Agarrado", self.janela.area.bolhas[-1]._texto.text())
        self.assertEqual(self.janela.selo.text(), "🧙 Assistente")

    def test_varios_chats(self):
        self.janela.entrada.setPlainText("Como funciona a condição Agarrado?")
        self.janela.btn_enviar.click()
        self.assertTrue(self.esperar(lambda: not self.janela.ocupado and self.janela.area.quantidade >= 3))
        self.janela._novo_chat()
        self.assertEqual(self.janela.lista.count(), 2)
        self.assertEqual(self.janela.area.quantidade, 1)
        self.janela.lista.setCurrentRow(1)
        self.assertEqual(self.janela.area.quantidade, 3)


if __name__ == "__main__":
    unittest.main()