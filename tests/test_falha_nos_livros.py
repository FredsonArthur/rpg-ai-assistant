"""
Falhas na consulta aos livros (rpgassistant/services/rag.py)
------------------------------------------------------------
O Mestre consulta os livros a cada turno por `rag.recuperar_contexto`, que promete nunca levantar erro.
Estes testes conferem que a promessa vale para qualquer falha da busca (Chroma, embeddings, disco), e não
só para a base ainda não indexada, e que um turno do Mestre não deixa a pergunta do jogador solta no chat.
"""

import logging
import types
import unittest
from unittest import mock

from rpgassistant.core.chats import GerenciadorDeChats
from rpgassistant.core.controller import ControladorDeChat
from rpgassistant.services import rag
from rpgassistant.storage.database import Database
from rpgassistant.storage.repository import RepositorioChats
from tests.helpers import BaseTeste, OllamaFalso, RelogioFalso, modelo


class BancoQueFalha:
    """Base vetorial de mentira cuja busca sempre falha, como um Chroma com problema."""

    def __init__(self) -> None:
        self._collection = types.SimpleNamespace(metadata=None)

    def similarity_search_with_score(self, query, k):
        raise RuntimeError("erro interno do Chroma")


class RecuperarContextoComFalhaTest(BaseTeste):
    def test_falha_na_busca_nao_levanta_erro(self):
        with mock.patch.object(rag, "_vector_store", BancoQueFalha()):
            contexto, fontes = rag.recuperar_contexto("agarrar")
        self.assertIn("não puderam ser consultados", contexto)
        self.assertEqual(fontes, "Nenhuma fonte")

    def test_falha_ao_carregar_a_base_nao_levanta_erro(self):
        """Por exemplo: não foi possível carregar o modelo de embeddings."""
        with mock.patch.object(rag, "load_vector_store", side_effect=OSError("sem rede para baixar os embeddings")):
            contexto, fontes = rag.recuperar_contexto("agarrar")
        self.assertIn("não puderam ser consultados", contexto)
        self.assertEqual(fontes, "Nenhuma fonte")

    def test_a_falha_e_registrada_no_log(self):
        logging.disable(logging.NOTSET)  # tests/__init__.py desliga os logs; aqui eles precisam funcionar
        self.addCleanup(logging.disable, logging.CRITICAL)
        with mock.patch.object(rag, "_vector_store", BancoQueFalha()), self.assertLogs(rag.logger, "WARNING") as logs:
            rag.recuperar_contexto("agarrar")
        self.assertIn("erro interno do Chroma", "\n".join(logs.output))

    def test_base_nao_indexada_continua_com_o_aviso_proprio(self):
        with mock.patch.object(rag, "_vector_store", None):  # não há pasta vectordb neste teste
            contexto, fontes = rag.recuperar_contexto("agarrar")
        self.assertIn("Base vetorial não inicializada", contexto)
        self.assertEqual(fontes, "Nenhuma fonte")

    def test_buscar_contexto_continua_levantando_o_erro(self):
        """Só a versão tolerante engole a falha: o Assistente precisa saber que a busca não funcionou."""
        with mock.patch.object(rag, "_vector_store", BancoQueFalha()):
            with self.assertRaises(RuntimeError):
                rag.buscar_contexto("agarrar")


class MestreSemOsLivrosTest(BaseTeste):
    def setUp(self):
        super().setUp()
        self.ger = GerenciadorDeChats(RepositorioChats(Database(":memory:"), agora=RelogioFalso()))
        self.addCleanup(self.ger.fechar)
        self.c = ControladorDeChat(self.ger)
        self.falso = self.usar_ollama(OllamaFalso(responder=modelo))
        padrao = mock.patch.object(rag, "_vector_store", BancoQueFalha())
        padrao.start()
        self.addCleanup(padrao.stop)
        # Um chat do Mestre já com a aventura em andamento.
        chat = self.ger.repositorio.criar_chat(
            modo="mestre", estado={"cenario": "Tumba", "personagem": "Guerreiro", "estado_combate": ""})
        self.ger.registrar(chat.id, "assistant", "Você vê um corredor escuro. O que você faz?")
        self.chat_id = chat.id

    def rotulos(self):
        return [(m.papel, m.tipo) for m in self.ger.mensagens(self.chat_id)]

    def test_o_turno_segue_sem_os_livros_e_nao_deixa_a_pergunta_solta(self):
        turno = self.c.enviar(self.chat_id, "Ataco o goblin")  # antes, a busca com falha levantava erro aqui
        list(turno.tokens())
        resposta = turno.concluir()
        self.assertEqual(resposta.extras["fontes"], "Nenhuma fonte")
        self.assertEqual(self.rotulos(), [("assistant", "fala"), ("user", "fala"), ("assistant", "fala")])
        # O modelo foi avisado de que os livros não estavam disponíveis.
        sistema = self.falso.chamadas[-1]["messages"][0]["content"]
        self.assertIn("não puderam ser consultados", sistema)

    def test_a_acao_seguinte_tambem_funciona(self):
        for acao in ("Ataco o goblin", "Ataco de novo"):
            turno = self.c.enviar(self.chat_id, acao)
            list(turno.tokens())
            turno.concluir()
        self.assertEqual(len(self.rotulos()), 5)  # abertura + 2 ações + 2 respostas


if __name__ == "__main__":
    unittest.main()