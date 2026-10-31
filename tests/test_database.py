import sqlite3
import threading
import unittest
from pathlib import Path
import tempfile

from rpgassistant.errors import BancoDeDadosError
from rpgassistant.storage.database import MEMORIA, VERSAO_ATUAL, Database


class DatabaseTest(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.pasta = Path(pasta.name)
        self.caminho = self.pasta / "dados" / "chats.db"

    def abrir(self, caminho=None) -> Database:
        db = Database(caminho or self.caminho)
        self.addCleanup(db.fechar)
        return db

    def test_cria_o_esquema_e_a_pasta(self):
        db = self.abrir()
        self.assertTrue(self.caminho.exists())
        tabelas = {l["name"] for l in db.consultar("SELECT name FROM sqlite_master WHERE type = 'table'")}
        self.assertTrue({"chats", "mensagens"} <= tabelas)
        self.assertEqual(db.versao, VERSAO_ATUAL)

    def test_banco_em_memoria(self):
        db = self.abrir(MEMORIA)
        self.assertEqual(db.versao, VERSAO_ATUAL)

    def test_reabrir_nao_repete_a_migracao_nem_perde_dados(self):
        db = self.abrir()
        db.executar("INSERT INTO chats (titulo, criado_em, atualizado_em) VALUES ('a', 'x', 'x')")
        db.fechar()
        outro = self.abrir()
        self.assertEqual(outro.valor("SELECT COUNT(*) FROM chats"), 1)
        self.assertEqual(outro.versao, VERSAO_ATUAL)

    def test_arquivo_que_nao_e_um_banco(self):
        self.caminho.parent.mkdir(parents=True)
        self.caminho.write_bytes(b"isto nao e um banco de dados sqlite " * 50)
        with self.assertRaises(BancoDeDadosError) as ctx:
            Database(self.caminho)
        self.assertIn("renomeie", str(ctx.exception))

    def test_banco_de_versao_mais_nova_e_recusado(self):
        db = self.abrir()
        db.executar(f"PRAGMA user_version = {VERSAO_ATUAL + 5}")
        db.fechar()
        with self.assertRaises(BancoDeDadosError) as ctx:
            Database(self.caminho)
        self.assertIn("mais nova", str(ctx.exception))

    def test_chaves_estrangeiras_ativas(self):
        db = self.abrir()
        self.assertEqual(db.valor("PRAGMA foreign_keys"), 1)
        with self.assertRaises(sqlite3.IntegrityError):
            db.executar("INSERT INTO mensagens (chat_id, ordem, papel, conteudo, criado_em) VALUES (99, 1, 'user', 'x', 'x')")

    def test_modo_wal_em_arquivo(self):
        self.assertEqual(self.abrir().valor("PRAGMA journal_mode").lower(), "wal")

    def test_transacao_confirma(self):
        db = self.abrir()
        with db.transaction():
            db.executar("INSERT INTO chats (titulo, criado_em, atualizado_em) VALUES ('a', 'x', 'x')")
        self.assertEqual(db.valor("SELECT COUNT(*) FROM chats"), 1)

    def test_transacao_desfaz_tudo_se_der_erro(self):
        db = self.abrir()
        with self.assertRaises(RuntimeError):
            with db.transaction():
                db.executar("INSERT INTO chats (titulo, criado_em, atualizado_em) VALUES ('a', 'x', 'x')")
                raise RuntimeError("falha no meio")
        self.assertEqual(db.valor("SELECT COUNT(*) FROM chats"), 0)
        with db.transaction():  # e o banco continua utilizável
            db.executar("INSERT INTO chats (titulo, criado_em, atualizado_em) VALUES ('b', 'x', 'x')")
        self.assertEqual(db.valor("SELECT COUNT(*) FROM chats"), 1)

    def test_transacoes_aninhadas_viram_uma(self):
        db = self.abrir()
        with self.assertRaises(RuntimeError):
            with db.transaction():
                with db.transaction():
                    db.executar("INSERT INTO chats (titulo, criado_em, atualizado_em) VALUES ('a', 'x', 'x')")
                raise RuntimeError("falha depois da interna")
        self.assertEqual(db.valor("SELECT COUNT(*) FROM chats"), 0)

    def test_pode_ser_usado_de_outra_thread(self):
        db = self.abrir()
        erros = []

        def gravar():
            try:
                db.executar("INSERT INTO chats (titulo, criado_em, atualizado_em) VALUES ('t', 'x', 'x')")
            except Exception as e:  # pragma: no cover
                erros.append(e)

        thread = threading.Thread(target=gravar)
        thread.start()
        thread.join()
        self.assertEqual(erros, [])
        self.assertEqual(db.valor("SELECT COUNT(*) FROM chats"), 1)

    def test_fechar_duas_vezes(self):
        db = self.abrir()
        db.fechar()
        db.fechar()


if __name__ == "__main__":
    unittest.main()