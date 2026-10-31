import unittest
from dataclasses import replace
from unittest import mock

from rpgassistant import config
from rpgassistant.errors import OllamaError
from rpgassistant.services import llm
from tests.helpers import BaseTeste, OllamaFalso, pedacos

MSG = [{"role": "user", "content": "oi"}]


class ChatLlmTest(BaseTeste):
    def test_envia_modelo_mensagens_e_opcoes_da_configuracao(self):
        falso = self.usar_ollama(OllamaFalso("resposta"))
        resp = llm.chat_llm(MSG, temperature=0.3)
        self.assertEqual(resp["message"]["content"], "resposta")
        chamada = falso.chamadas[0]
        self.assertEqual(chamada["model"], "llama3")
        self.assertEqual(chamada["messages"], MSG)
        self.assertEqual(chamada["options"], {"num_ctx": 8192, "temperature": 0.3})

    def test_opcoes_extras(self):
        falso = self.usar_ollama(OllamaFalso())
        llm.chat_llm(MSG, temperature=0, num_predict=100)
        self.assertEqual(falso.chamadas[0]["options"]["num_predict"], 100)

    def test_usa_a_configuracao_atual(self):
        novo = replace(self.cfg, ollama_model="llama3.1", ollama_num_ctx=4096)
        falso = self.usar_ollama(OllamaFalso())
        with mock.patch.object(config, "settings", novo):
            llm.chat_llm(MSG, temperature=0.5)
        self.assertEqual((falso.chamadas[0]["model"], falso.chamadas[0]["options"]["num_ctx"]), ("llama3.1", 4096))

    def test_falha_vira_ollama_error_com_instrucao(self):
        self.usar_ollama(OllamaFalso(falha=ConnectionError("fora do ar")))
        with self.assertRaises(OllamaError) as ctx:
            llm.chat_llm(MSG, temperature=0.3)
        self.assertIn("fora do ar", str(ctx.exception))
        self.assertIn("ollama pull llama3", str(ctx.exception))


class StreamTest(BaseTeste):
    def test_pedacos_texto_final_e_metricas(self):
        falso = self.usar_ollama(OllamaFalso(chunks=["Olá", ", ", "mundo"]))
        stream = llm.chat_llm_stream(MSG, temperature=0.3)
        self.assertEqual(list(stream.tokens()), ["Olá", ", ", "mundo"])
        self.assertEqual(stream.texto, "Olá, mundo")
        self.assertEqual((stream.prompt_tokens, stream.completion_tokens), (11, 5))
        self.assertTrue(falso.chamadas[0]["stream"])

    def test_erro_ao_abrir_o_stream(self):
        self.usar_ollama(OllamaFalso(falha=ConnectionError("fora do ar")))
        with self.assertRaises(OllamaError):
            llm.chat_llm_stream(MSG, temperature=0.3)

    def test_erro_no_meio_da_geracao_preserva_o_texto_parcial(self):
        def gerar(kwargs):
            yield {"message": {"content": "par"}}
            raise ConnectionError("caiu")
        self.usar_ollama(OllamaFalso(responder=gerar))
        stream = llm.chat_llm_stream(MSG, temperature=0.3)
        recebido = []
        with self.assertRaises(OllamaError):
            for parte in stream.tokens():
                recebido.append(parte)
        self.assertEqual(recebido, ["par"])
        self.assertEqual(stream.texto, "par")

    def test_pedacos_vazios_sao_ignorados(self):
        stream = llm.RespostaEmStream(pedacos(["a", "", "b"]))
        self.assertEqual(list(stream.tokens()), ["a", "b"])


if __name__ == "__main__":
    unittest.main()