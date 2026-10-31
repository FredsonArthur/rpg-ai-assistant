import unittest

from rpgassistant.errors import OllamaError
from rpgassistant.modes import assistente
from tests.helpers import BaseTeste, OllamaFalso, pedacos, resposta

HISTORICO = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]


def modelo(kwargs):
    """Ollama falso: reescreve perguntas, responde em stream ou de uma vez."""
    if len(kwargs["messages"]) == 1:
        return resposta("Pergunta reescrita sobre cegueira?")
    if kwargs.get("stream"):
        return pedacos(["Resp", "osta"], final=(7, 3))
    return resposta("RESP", prompt_tokens=7, completion_tokens=3)


class FormatarMetricasTest(unittest.TestCase):
    def test_formato(self):
        self.assertEqual(assistente.formatar_metricas(10, 2, "q", "q"), "Prompt Tokens: 10 | Completion Tokens: 2")
        self.assertIn("Busca reescrita: nova", assistente.formatar_metricas(10, 2, "nova", "q"))


class ResponderTest(BaseTeste):
    def test_resposta_fontes_e_metricas_com_busca_reescrita(self):
        self.usar_ollama(OllamaFalso(responder=modelo))
        consultas = self.usar_busca()
        resp, fontes, metricas = assistente.responder("e se?", HISTORICO)
        self.assertEqual((resp, fontes), ("RESP", "Core | PHB"))
        self.assertIn("Prompt Tokens: 7", metricas)
        self.assertIn("Busca reescrita: Pergunta reescrita sobre cegueira?", metricas)
        self.assertEqual(consultas, [("Pergunta reescrita sobre cegueira?", 8)])

    def test_monta_system_historico_e_pergunta(self):
        falso = self.usar_ollama(OllamaFalso(responder=modelo))
        self.usar_busca("CTX")
        assistente.responder("e se?", HISTORICO)
        mensagens = falso.chamadas[-1]["messages"]
        self.assertEqual(mensagens[0]["role"], "system")
        self.assertIn("CTX", mensagens[0]["content"])
        self.assertEqual(mensagens[1:], HISTORICO + [{"role": "user", "content": "e se?"}])
        self.assertEqual(falso.chamadas[-1]["options"], {"num_ctx": 8192, "temperature": 0.3})

    def test_sem_historico_so_a_chamada_principal(self):
        falso = self.usar_ollama(OllamaFalso(responder=modelo))
        self.usar_busca()
        assistente.responder("Como funciona agarrar?")
        self.assertEqual(len(falso.chamadas), 1)

    def test_janela_de_historico(self):
        falso = self.usar_ollama(OllamaFalso(responder=modelo))
        self.usar_busca()
        historico = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(14)]
        assistente.responder("e se?", historico)
        mensagens = falso.chamadas[-1]["messages"]
        self.assertEqual(len(mensagens), 1 + 10 + 1)
        self.assertEqual(mensagens[1]["content"], "m4")

    def test_falha_do_ollama_levanta_ollama_error(self):
        self.usar_ollama(OllamaFalso(falha=ConnectionError("fora do ar")))
        self.usar_busca()
        with self.assertRaises(OllamaError):
            assistente.responder("pergunta")


class ResponderStreamTest(BaseTeste):
    def test_stream_consulta_e_fontes(self):
        falso = self.usar_ollama(OllamaFalso(responder=modelo))
        self.usar_busca()
        stream, fontes, consulta = assistente.responder_stream("e se?", HISTORICO)
        self.assertEqual(list(stream.tokens()), ["Resp", "osta"])
        self.assertEqual((stream.texto, fontes, consulta), ("Resposta", "Core | PHB", "Pergunta reescrita sobre cegueira?"))
        self.assertEqual((stream.prompt_tokens, stream.completion_tokens), (7, 3))
        self.assertTrue(falso.chamadas[-1]["stream"])


if __name__ == "__main__":
    unittest.main()


class PrepararTest(BaseTeste):
    """O fluxo "só os livros": reescrita, busca, barreira de relevância e montagem do prompt."""

    def test_pergunta_relevante_monta_o_prompt_dos_livros(self):
        self.usar_ollama(OllamaFalso(responder=modelo))
        busca = self.usar_busca("CTX-LIVROS", "Core | PHB", similaridade=0.62)
        consulta = assistente.preparar("e se?", HISTORICO)
        self.assertFalse(consulta.recusada)
        self.assertEqual((consulta.fontes, consulta.melhor_similaridade), ("Core | PHB", 0.62))
        self.assertEqual(consulta.consulta_busca, "Pergunta reescrita sobre cegueira?")
        self.assertEqual(busca, [("Pergunta reescrita sobre cegueira?", 8)])
        sistema = consulta.mensagens[0]["content"]
        self.assertIn("SOMENTE", sistema)
        self.assertIn("CTX-LIVROS", sistema)
        self.assertEqual(consulta.mensagens[1:], HISTORICO + [{"role": "user", "content": "e se?"}])

    def test_abaixo_do_limiar_recusa_sem_chamar_o_modelo(self):
        falso = self.usar_ollama(OllamaFalso())
        self.usar_busca(similaridade=0.12)
        consulta = assistente.preparar("O que é uma rede neural?")
        self.assertTrue(consulta.recusada)
        self.assertEqual((consulta.mensagens, consulta.fontes), ([], ""))
        self.assertIn("0.12", consulta.motivo_recusa)
        self.assertEqual(falso.chamadas, [])

    def test_no_limiar_passa_e_limiar_zero_desliga_a_barreira(self):
        self.usar_ollama(OllamaFalso())
        busca = self.usar_busca(similaridade=0.30)
        self.assertFalse(assistente.preparar("x").recusada)
        busca.similaridade = 0.05
        self.assertTrue(assistente.preparar("x").recusada)
        from dataclasses import replace
        from unittest import mock
        from rpgassistant import config
        with mock.patch.object(config, "settings", replace(self.cfg, relevancia_minima=0.0)):
            self.assertFalse(assistente.preparar("x").recusada)

    def test_sem_trechos_recusa(self):
        self.usar_ollama(OllamaFalso())
        self.usar_busca(similaridade=None)
        self.assertTrue(assistente.preparar("x").recusada)

    def test_base_nao_indexada_levanta_erro(self):
        from rpgassistant.errors import BaseVaziaError
        self.usar_ollama(OllamaFalso())
        self.usar_busca().base_vazia = True
        with self.assertRaises(BaseVaziaError):
            assistente.preparar("x")

    def test_iniciar_stream_usa_a_temperatura_do_assistente(self):
        falso = self.usar_ollama(OllamaFalso(chunks=["Olá"]))
        self.usar_busca()
        stream = assistente.iniciar_stream(assistente.preparar("x"))
        self.assertEqual(list(stream.tokens()), ["Olá"])
        self.assertEqual(falso.chamadas[-1]["options"]["temperature"], 0.3)