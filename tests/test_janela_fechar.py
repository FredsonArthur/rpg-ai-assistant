"""
Testes do fechamento da janela (JanelaPrincipal.closeEvent), com o Qt falso de tests/qt_falso.py.

No Qt falso as threads rodam de forma síncrona, então nunca há uma thread "presa". Para simular uma,
os testes colocam em `janela._threads` (ou em `janela._ollama_thread`) uma `ThreadDeMentira`, que
registra tudo o que a janela faz com ela.
"""

import sys
import unittest
from unittest import mock

from rpgassistant.core.chats import GerenciadorDeChats
from rpgassistant.core.controller import ControladorDeChat
from rpgassistant.storage.database import Database
from rpgassistant.storage.repository import RepositorioChats
from tests import qt_falso
from tests.helpers import BaseTeste, RelogioFalso


def setUpModule():
    # Coloca o Qt falso no lugar do PySide6 antes de importar rpgassistant.ui.janela.
    qt_falso.instalar()


def tearDownModule():
    # Devolve os módulos originais, para não afetar os outros arquivos de teste.
    qt_falso.remover()


def widgets():
    """O módulo de widgets do Qt falso (onde ficam QMessageBox e companhia)."""
    return sys.modules["PySide6.QtWidgets"]


class ThreadDeMentira:
    """
    Faz o papel de uma QThread. `trava=True` simula uma thread presa numa chamada ao modelo: `wait` só
    devolve True depois de `terminate`. `trava=False` simula uma thread que termina dentro do prazo.
    Cada chamada recebida fica em `chamadas`, na ordem.
    """

    def __init__(self, trava: bool) -> None:
        self.trava = trava
        self.rodando = True
        self.chamadas = []

    def isRunning(self) -> bool:
        return self.rodando

    def parar(self) -> None:
        self.chamadas.append("parar")

    def wait(self, ms: int = 0) -> bool:
        self.chamadas.append(("wait", ms))
        return not self.rodando or not self.trava

    def terminate(self) -> None:
        self.chamadas.append("terminate")
        self.rodando = False


class EventoDeFechar:
    """Evento de fechamento de mentira: guarda se a janela chamou `ignore()` (cancelou o fechamento)."""

    def __init__(self) -> None:
        self.ignorado = False

    def ignore(self) -> None:
        self.ignorado = True


class FecharJanelaTest(BaseTeste):
    def setUp(self):
        super().setUp()
        from rpgassistant.ui import janela as modulo_janela
        from rpgassistant.ui.janela import JanelaPrincipal

        self.prazos = modulo_janela  # as constantes de tempo (ESPERA_*) ficam no módulo da janela
        self.ger = GerenciadorDeChats(RepositorioChats(Database(":memory:"), agora=RelogioFalso()))
        self.addCleanup(self.ger.fechar)
        widgets().QMessageBox.chamadas.clear()
        widgets().QMessageBox.resposta = widgets().QMessageBox.StandardButton.Yes
        self.janela = JanelaPrincipal(ControladorDeChat(self.ger), iniciar_ollama=False)

    def fechar(self):
        """
        Fecha a janela. O fechamento do banco é substituído por um espião, para os testes ainda poderem
        consultar o banco depois. Devolve (evento, espião do fechamento do banco).
        """
        evento = EventoDeFechar()
        with mock.patch.object(self.ger, "fechar") as fechar_banco:
            self.janela.closeEvent(evento)
        return evento, fechar_banco

    def pendente(self):
        """Uma pergunta salva no chat atual e ainda sem resposta, como a de um turno em andamento."""
        chat = self.ger.chat_atual
        mensagem = self.ger.registrar(chat.id, "user", "pergunta sem resposta")
        self.janela._pendentes = [mensagem]
        return chat.id, mensagem

    def ids_das_mensagens(self, chat_id):
        return [m.id for m in self.ger.mensagens(chat_id)]

    def test_sem_resposta_em_andamento_fecha_sem_perguntar(self):
        evento, fechar_banco = self.fechar()
        self.assertEqual(widgets().QMessageBox.chamadas, [])  # nada de confirmação
        self.assertFalse(evento.ignorado)
        self.assertTrue(self.janela.fechada)
        fechar_banco.assert_called_once()

    def test_usuario_desiste_de_fechar(self):
        thread = ThreadDeMentira(trava=True)
        self.janela._threads.append(thread)
        widgets().QMessageBox.resposta = widgets().QMessageBox.StandardButton.No
        evento, fechar_banco = self.fechar()
        self.assertTrue(evento.ignorado)
        self.assertFalse(self.janela.fechada)
        self.assertFalse(self.janela._encerrando)
        self.assertEqual(thread.chamadas, [])  # a thread nem foi tocada
        fechar_banco.assert_not_called()

    def test_thread_que_termina_no_prazo_nao_e_encerrada_a_forca(self):
        thread = ThreadDeMentira(trava=False)
        self.janela._threads.append(thread)
        chat_id, mensagem = self.pendente()
        evento, fechar_banco = self.fechar()
        self.assertEqual(len(widgets().QMessageBox.chamadas), 1)  # perguntou uma vez
        self.assertEqual(thread.chamadas, ["parar", ("wait", self.prazos.ESPERA_TURNO_MS)])
        # Quem desfaz a pergunta, nesse caminho, é o controlador, não a janela.
        self.assertIn(mensagem.id, self.ids_das_mensagens(chat_id))
        self.assertTrue(self.janela.fechada)
        fechar_banco.assert_called_once()

    def test_thread_presa_e_encerrada_e_a_pergunta_pendente_e_desfeita(self):
        thread = ThreadDeMentira(trava=True)
        self.janela._threads.append(thread)
        chat_id, mensagem = self.pendente()
        evento, fechar_banco = self.fechar()
        self.assertEqual(thread.chamadas, [
            "parar",
            ("wait", self.prazos.ESPERA_TURNO_MS),
            "terminate",
            ("wait", self.prazos.ESPERA_APOS_TERMINAR_MS),
        ])
        self.assertNotIn(mensagem.id, self.ids_das_mensagens(chat_id))  # a pergunta sem resposta sumiu
        self.assertTrue(self.janela.fechada)
        fechar_banco.assert_called_once()

    def test_thread_do_ollama_presa_e_encerrada_sem_perguntar(self):
        ollama = ThreadDeMentira(trava=True)
        self.janela._ollama_thread = ollama
        evento, fechar_banco = self.fechar()
        self.assertEqual(widgets().QMessageBox.chamadas, [])  # não há resposta da IA a perder
        self.assertEqual(ollama.chamadas, [
            ("wait", self.prazos.ESPERA_OLLAMA_MS),
            "terminate",
            ("wait", self.prazos.ESPERA_APOS_TERMINAR_MS),
        ])
        self.assertTrue(self.janela.fechada)
        fechar_banco.assert_called_once()


if __name__ == "__main__":
    unittest.main()