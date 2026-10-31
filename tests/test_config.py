import os
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from rpgassistant import config
from tests.helpers import BaseTeste


class ConfigTest(BaseTeste):
    def test_caminhos_derivam_da_pasta_de_dados(self):
        self.assertEqual(self.cfg.rulebooks_dir, self.pasta / "rulebooks")
        self.assertEqual(self.cfg.vectordb_dir, self.pasta / "vectordb")
        self.assertEqual(self.cfg.chats_db, self.pasta / "chats.db")

    def test_valores_padrao(self):
        padrao = config.Config()
        self.assertEqual((padrao.ollama_model, padrao.ollama_num_ctx), ("llama3", 8192))
        self.assertEqual((padrao.top_k_assistente, padrao.top_k_mestre, padrao.history_window), (8, 3, 10))
        self.assertEqual(padrao.data_dir, config.BASE_DIR / "data")

    def test_variaveis_de_ambiente(self):
        env = {"OLLAMA_MODEL": "llama3.1", "OLLAMA_NUM_CTX": "4096", "RPG_DATA_DIR": str(self.pasta)}
        with mock.patch.dict(os.environ, env):
            cfg = config.Config.from_env()
        self.assertEqual((cfg.ollama_model, cfg.ollama_num_ctx, cfg.data_dir), ("llama3.1", 4096, self.pasta))

    def test_sem_variaveis_usa_o_padrao(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = config.Config.from_env()
        self.assertEqual((cfg.ollama_model, cfg.ollama_num_ctx), ("llama3", 8192))

    def test_numero_invalido_explica_o_problema(self):
        with mock.patch.dict(os.environ, {"OLLAMA_NUM_CTX": "muito"}):
            with self.assertRaisesRegex(ValueError, "OLLAMA_NUM_CTX"):
                config.Config.from_env()

    def test_relevancia_minima(self):
        self.assertEqual(config.Config().relevancia_minima, 0.30)
        for texto, esperado in (("0.45", 0.45), ("0,5", 0.5), ("0", 0.0), ("1", 1.0)):
            with self.subTest(texto=texto), mock.patch.dict(os.environ, {"RPG_RELEVANCIA_MINIMA": texto}):
                self.assertEqual(config.Config.from_env().relevancia_minima, esperado)

    def test_relevancia_minima_invalida(self):
        for texto in ("alto", "1.5", "-0.1"):
            with self.subTest(texto=texto), mock.patch.dict(os.environ, {"RPG_RELEVANCIA_MINIMA": texto}):
                with self.assertRaisesRegex(ValueError, "RPG_RELEVANCIA_MINIMA"):
                    config.Config.from_env()

    def test_temperatura_por_arquetipo(self):
        self.assertEqual(self.cfg.temperatura_do_arquetipo("Tático"), 0.3)
        self.assertEqual(self.cfg.temperatura_do_arquetipo("Roleplay"), 0.8)
        self.assertEqual(self.cfg.temperatura_do_arquetipo("Inexistente"), self.cfg.temperatura_arquetipo_padrao)

    def test_configuracao_e_imutavel(self):
        with self.assertRaises(Exception):
            self.cfg.ollama_model = "outro"
        self.assertEqual(replace(self.cfg, ollama_model="outro").ollama_model, "outro")

    def test_garantir_pastas_cria_a_pasta_dos_livros(self):
        self.assertFalse(self.cfg.rulebooks_dir.exists())
        self.cfg.garantir_pastas()
        self.assertTrue(self.cfg.rulebooks_dir.is_dir())

    def test_importar_o_modulo_nao_cria_pastas(self):
        self.assertFalse(Path(self.pasta / "vectordb").exists())


if __name__ == "__main__":
    unittest.main()