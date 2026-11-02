import socket
import threading
import time
import unittest
from unittest import mock

from rpgassistant.services import ollama_service as svc


def porta_livre() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    porta = s.getsockname()[1]
    s.close()
    return porta


class OllamaServiceTest(unittest.TestCase):
    def test_porta_aberta_e_fechada(self):
        servidor = socket.socket()
        self.addCleanup(servidor.close)
        servidor.bind(("127.0.0.1", 0))
        servidor.listen(5)
        self.assertTrue(svc.ollama_ativo("127.0.0.1", servidor.getsockname()[1]))
        self.assertFalse(svc.ollama_ativo("127.0.0.1", porta_livre()))

    def test_ja_ativo_nao_inicia_nada(self):
        servidor = socket.socket()
        self.addCleanup(servidor.close)
        servidor.bind(("127.0.0.1", 0))
        servidor.listen(5)
        with mock.patch.object(svc.subprocess, "Popen") as popen:
            self.assertTrue(svc.iniciar_ollama(1, "127.0.0.1", servidor.getsockname()[1]))
        popen.assert_not_called()

    def test_desiste_depois_do_prazo(self):
        with mock.patch.object(svc.subprocess, "Popen") as popen:
            inicio = time.monotonic()
            self.assertFalse(svc.iniciar_ollama(0.8, "127.0.0.1", porta_livre()))
        self.assertEqual(popen.call_args[0][0], ["ollama", "serve"])
        self.assertGreaterEqual(time.monotonic() - inicio, 0.7)

    def test_espera_o_servico_subir(self):
        porta = porta_livre()
        abertos = []

        def subir_depois(cmd, **kwargs):
            def abrir():
                time.sleep(0.5)
                s = socket.socket()
                s.bind(("127.0.0.1", porta))
                s.listen(5)
                abertos.append(s)
            threading.Thread(target=abrir, daemon=True).start()

        self.addCleanup(lambda: [s.close() for s in abertos])
        with mock.patch.object(svc.subprocess, "Popen", subir_depois):
            self.assertTrue(svc.iniciar_ollama(5, "127.0.0.1", porta))

    def test_processo_destacado_no_linux_e_no_windows(self):
        with mock.patch.object(svc.sys, "platform", "linux"):
            self.assertEqual(svc._opcoes_do_processo(), {"start_new_session": True})
        with mock.patch.object(svc.sys, "platform", "win32"):
            opcoes = svc._opcoes_do_processo()
        self.assertEqual(list(opcoes), ["creationflags"])
        self.assertEqual(opcoes["creationflags"] & 0x08000000, 0x08000000)  # sem janela de console

    def test_popen_recebe_as_opcoes_do_sistema(self):
        with mock.patch.object(svc.subprocess, "Popen") as popen, mock.patch.object(svc.sys, "platform", "win32"):
            svc.iniciar_ollama(0.1, "127.0.0.1", porta_livre())
        self.assertIn("creationflags", popen.call_args.kwargs)
        self.assertNotIn("start_new_session", popen.call_args.kwargs)

    def test_ollama_nao_instalado(self):
        with mock.patch.object(svc.subprocess, "Popen", side_effect=FileNotFoundError("ollama")):
            self.assertFalse(svc.iniciar_ollama(1, "127.0.0.1", porta_livre()))


if __name__ == "__main__":
    unittest.main()