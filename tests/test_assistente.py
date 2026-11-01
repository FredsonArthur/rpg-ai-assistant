import unittest

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