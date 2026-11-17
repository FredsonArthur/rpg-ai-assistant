"""
Testes dos comandos do chat que começam com "/" (core/controller.py: ler_comando e enviar).

Regra: é comando um texto que começa com um comando conhecido ou uma palavra só que começa com "/".
Um texto com várias palavras, como "/me ataca o goblin", é uma mensagem normal e vai ao modelo.
"""

import unittest

from rpgassistant.core import controller as ctl
from tests.test_controller import ControladorBase, executar


class LerComandoTest(unittest.TestCase):
    def test_comandos_conhecidos(self):
        for texto in ("/ajuda", "/feedback", "/assistente", "/mestre", "/jogador"):
            with self.subTest(texto=texto):
                self.assertEqual(ctl.ler_comando(texto), texto)

    def test_ignora_maiusculas_e_acentos(self):
        self.assertEqual(ctl.ler_comando("/AJUDA"), "/ajuda")
        self.assertEqual(ctl.ler_comando("/Assistênte"), "/assistente")

    def test_comando_conhecido_com_texto_depois_continua_sendo_comando(self):
        self.assertEqual(ctl.ler_comando("/ajuda por favor"), "/ajuda")
        self.assertEqual(ctl.ler_comando("/feedback da sessão"), "/feedback")

    def test_uma_palavra_desconhecida_ainda_e_comando(self):
        """Um erro de digitação como "/ajud" mostra a ajuda, em vez de ir ao modelo."""
        self.assertEqual(ctl.ler_comando("/ajud"), "/ajud")
        self.assertEqual(ctl.ler_comando("/xyz"), "/xyz")
        self.assertEqual(ctl.ler_comando("/"), "/")

    def test_varias_palavras_desconhecidas_nao_sao_comando(self):
        for texto in ("/me ataca o goblin", "/me sorri", "/rola d20 para Percepção"):
            with self.subTest(texto=texto):
                self.assertEqual(ctl.ler_comando(texto), "")

    def test_texto_comum_nao_e_comando(self):
        for texto in ("Ataco o goblin", "oi", "Como funciona agarrar?", "a barra / no meio não conta"):
            with self.subTest(texto=texto):
                self.assertEqual(ctl.ler_comando(texto), "")


class ComandosNoChatTest(ControladorBase):
    def test_acao_com_barra_vai_ao_modelo_no_modo_mestre(self):
        chat_id = self.chat_mestre()
        turno = self.c.enviar(chat_id, "/me ataca o goblin")
        self.assertTrue(turno.precisa_modelo)
        _, resp = executar(turno)
        self.assertEqual(self.rotulos(chat_id)[-2:], [("user", "fala"), ("assistant", "fala")])
        self.assertEqual(self.ger.mensagens(chat_id)[-2].conteudo, "/me ataca o goblin")
        self.assertNotEqual(resp.tipo, "ajuda")

    def test_fala_com_barra_vai_ao_modelo_no_modo_jogador(self):
        chat_id = self.chat_jogador()
        turno = self.c.enviar(chat_id, "/me abre a porta da taverna")
        self.assertTrue(turno.precisa_modelo)
        executar(turno)
        self.assertEqual(self.ger.historico_para_llm(chat_id)[-2]["content"], "/me abre a porta da taverna")

    def test_pergunta_com_barra_vai_ao_modelo_no_modo_assistente(self):
        chat_id = self.novo_chat("1")
        turno = self.c.enviar(chat_id, "/regra Como funciona a condição Agarrado?")
        self.assertTrue(turno.precisa_modelo)

    def test_uma_palavra_desconhecida_mostra_a_ajuda_em_qualquer_modo(self):
        for abrir in (lambda: self.novo_chat("1"), self.chat_mestre, self.chat_jogador):
            with self.subTest(abrir=abrir):
                chat_id = abrir()
                turno = self.c.enviar(chat_id, "/ajud")
                self.assertFalse(turno.precisa_modelo)
                self.assertEqual(turno.salvas[-1].tipo, "ajuda")

    def test_ajuda_com_texto_depois_mostra_a_ajuda(self):
        chat_id = self.chat_mestre()
        turno = self.c.enviar(chat_id, "/ajuda por favor")
        self.assertFalse(turno.precisa_modelo)
        self.assertEqual(turno.salvas[-1].tipo, "ajuda")

    def test_a_ajuda_explica_a_regra(self):
        turno = self.c.enviar(self.novo_chat("1"), "/ajuda")
        self.assertIn("/me ataca", turno.salvas[-1].conteudo)

    def test_comandos_nao_sao_enviados_ao_modelo(self):
        chat_id = self.chat_mestre()
        antes = len(self.falso.chamadas)
        self.c.enviar(chat_id, "/ajuda")
        self.c.enviar(chat_id, "/xyz")
        self.assertEqual(len(self.falso.chamadas), antes)
        self.assertEqual(self.ger.historico_para_llm(chat_id)[-1]["role"], "assistant")  # nada entrou no histórico


if __name__ == "__main__":
    unittest.main()