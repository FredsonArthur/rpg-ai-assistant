"""
Robustez do banco de chats e da busca nos livros
------------------------------------------------
Testes de proteção (contra regressão) para dois comportamentos que já funcionam e que alguém poderia
quebrar sem querer:

1. Dois escritores no mesmo arquivo de chats: o segundo ESPERA o primeiro terminar, em vez de falhar na
   hora. (O `sqlite3.connect` do Python espera até 5 segundos por padrão; isso vale também para dois
   processos abrindo o mesmo `chats.db`.)
2. A conversão de distância em similaridade não depende de um atributo privado do Chroma: se ele sumir
   numa versão futura, a base é tratada como L2, que é como o app sempre a cria.
"""

import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest import mock

from rpgassistant.services import rag
from rpgassistant.storage.database import Database
from tests.helpers import BaseTeste

INSERIR = "INSERT INTO chats (titulo, criado_em, atualizado_em) VALUES (?, 'x', 'x')"


class DoisEscritoresTest(unittest.TestCase):
    def test_o_segundo_escritor_espera_o_primeiro_terminar(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "chats.db"
            primeiro, segundo = Database(caminho), Database(caminho)  # como dois processos no mesmo arquivo
            try:
                segurando = threading.Event()

                def segurar():
                    with primeiro.transaction():
                        primeiro.executar(INSERIR, ("do primeiro",))
                        segurando.set()
                        time.sleep(1.0)  # mantém o banco bloqueado por um instante

                thread = threading.Thread(target=segurar)
                thread.start()
                segurando.wait()
                # Não pode levantar "database is locked": a gravação espera a transação do primeiro acabar.
                segundo.executar(INSERIR, ("do segundo",))
                thread.join()
                self.assertEqual(segundo.valor("SELECT COUNT(*) FROM chats"), 2)
            finally:
                primeiro.fechar()
                segundo.fechar()


class Doc:
    """Trecho de livro de mentira: só o que a busca lê."""

    def __init__(self, page_content, metadata):
        self.page_content, self.metadata = page_content, metadata


class BancoSemColecao:
    """Base vetorial sem o atributo privado `_collection`, como num Chroma que o tenha renomeado."""

    def similarity_search_with_score(self, query, k):
        return [(Doc("A", {"source": "/x/rulebooks/core/PHB.md"}), 0.6)]


class EspacoDaBaseTest(BaseTeste):
    def test_sem_o_atributo_privado_a_base_e_tratada_como_l2(self):
        self.assertEqual(rag._espaco_da_base(BancoSemColecao()), "l2")

    def test_metadado_ausente_tambem_e_l2(self):
        base = types.SimpleNamespace(_collection=types.SimpleNamespace(metadata=None))
        self.assertEqual(rag._espaco_da_base(base), "l2")

    def test_metadado_de_cosseno_e_respeitado(self):
        base = types.SimpleNamespace(_collection=types.SimpleNamespace(metadata={"hnsw:space": "cosine"}))
        self.assertEqual(rag._espaco_da_base(base), "cosine")

    def test_a_similaridade_continua_certa_sem_o_atributo_privado(self):
        with mock.patch.object(rag, "_vector_store", BancoSemColecao()):
            resultado = rag.buscar_contexto("agarrar", k=1)
        self.assertAlmostEqual(resultado.melhor_similaridade, 1 - 0.36 / 2)  # distância 0.6 em L2


if __name__ == "__main__":
    unittest.main()