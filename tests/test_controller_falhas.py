"""
Falhas inesperadas ao montar um turno (core/controller.py)
----------------------------------------------------------
1. Um erro qualquer ao montar o turno não pode deixar a pergunta do usuário salva no chat sem resposta
   (antes, só o OllamaError desfazia a pergunta).
2. Quando a busca nos livros falha por um problema técnico, o Assistente mostra uma mensagem clara, em vez de
   "Erro inesperado" (o erro vira BuscaNosLivrosError, que a janela mostra como está).
"""

import unittest
from unittest import mock

from rpgassistant.errors import BuscaNosLivrosError, RPGAssistantError
from rpgassistant.modes import assistente, jogador, mestre
from tests.test_controller import ControladorBase


class PerguntaSoltaTest(ControladorBase):
    """Se algo falhar depois de a pergunta ser salva, ela é desfeita e o erro continua subindo."""

    def conferir(self, chat_id, texto, modulo, funcao):
        antes = self.rotulos(chat_id)
        with mock.patch.object(modulo, funcao, side_effect=RuntimeError("falha inesperada")):
            with self.assertRaisesRegex(RuntimeError, "falha inesperada"):
                self.c.enviar(chat_id, texto)
        self.assertEqual(self.rotulos(chat_id), antes)  # nenhuma pergunta ficou solta

    def test_mestre(self):
        self.conferir(self.chat_mestre(), "Ataco o goblin", mestre, "run_master_turn_stream")

    def test_jogador(self):
        self.conferir(self.chat_jogador(), "Vocês entram na taverna.", jogador, "run_player_simulator_turn_stream")

    def test_assistente(self):
        self.conferir(self.novo_chat("1"), "Como funciona a condição Agarrado?", assistente, "iniciar_stream")


class FalhaNaBuscaDoAssistenteTest(ControladorBase):
    def test_erro_tecnico_da_busca_vira_mensagem_clara(self):
        chat_id = self.novo_chat("1")
        antes = self.rotulos(chat_id)
        self.busca.erro = RuntimeError("erro interno do Chroma")
        with self.assertRaises(BuscaNosLivrosError) as contexto:
            self.c.enviar(chat_id, "Como funciona a condição Agarrado?")
        mensagem = str(contexto.exception)
        self.assertIn("RuntimeError", mensagem)
        self.assertIn("erro interno do Chroma", mensagem)
        self.assertIn("rpgassistant.diagnostico", mensagem)
        self.assertIsInstance(contexto.exception.__cause__, RuntimeError)  # o erro original fica encadeado
        self.assertEqual(self.rotulos(chat_id), antes)  # nada foi salvo

    def test_biblioteca_faltando_nao_e_embrulhada(self):
        """ImportError segue como está: a janela mostra o comando "pip install -r requirements.txt"."""
        chat_id = self.novo_chat("1")
        self.busca.erro = ImportError("No module named 'langchain_chroma'", name="langchain_chroma")
        with self.assertRaises(ImportError):
            self.c.enviar(chat_id, "Como funciona a condição Agarrado?")

    def test_e_um_erro_do_dominio(self):
        """A janela mostra a mensagem dos erros do domínio como está, sem "Erro inesperado"."""
        self.assertTrue(issubclass(BuscaNosLivrosError, RPGAssistantError))

    def test_base_nao_indexada_continua_com_o_aviso_proprio(self):
        self.busca.base_vazia = True
        chat_id = self.novo_chat("1")
        turno = self.c.enviar(chat_id, "Como funciona a condição Agarrado?")
        self.assertFalse(turno.precisa_modelo)
        self.assertIn("rpgassistant.indexar", turno.salvas[-1].conteudo)


if __name__ == "__main__":
    unittest.main()