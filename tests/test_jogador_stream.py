"""
Testes das versões com streaming do modo Jogador (rpgassistant/modes/jogador.py):
`run_player_simulator_turn_stream` (a fala do jogador) e `iniciar_feedback_stream` (o feedback do mentor).
Os testes das versões sem streaming continuam em tests/test_jogador.py.
"""

import unittest

from rpgassistant.errors import OllamaError
from rpgassistant.modes import jogador
from rpgassistant.services import prompts
from tests.helpers import VALIDA, BaseTeste, OllamaFalso, pedacos


def historico(n):
    """Histórico de `n` mensagens alternando assistente e usuário, como o do chat."""
    return [{"role": "assistant" if i % 2 == 0 else "user", "content": f"m{i}"} for i in range(n)]


def streams_em_sequencia(*listas_de_pedacos):
    """
    Ollama falso que responde, a cada chamada, com a próxima lista de pedaços (em streaming).
    Cada argumento é a lista de pedaços de texto de uma chamada.
    """
    fila = iter(listas_de_pedacos)
    return lambda kwargs: pedacos(next(fila))


def consumir(resposta):
    """Itera o stream até o fim, como a thread da janela, e devolve os pedaços recebidos."""
    return list(resposta.tokens())


class FalaEmStreamTest(BaseTeste):
    def test_fala_valida_faz_uma_chamada_em_streaming(self):
        falso = self.usar_ollama(OllamaFalso(chunks=["[Ação]: Lia se afasta.\n", '[Fala]: "Posso rolar Percepção?"']))
        resposta = jogador.run_player_simulator_turn_stream(
            "Vocês entram na taverna.", "Lia. Maga Elfa, Nível 1", historico(30), "Roleplay")
        self.assertEqual(falso.chamadas, [])  # o modelo só é chamado quando a iteração começa

        partes = consumir(resposta)
        self.assertEqual("".join(partes), resposta.texto)
        self.assertTrue(jogador.formato_valido(resposta.texto))
        self.assertEqual(len(falso.chamadas), 1)
        chamada = falso.chamadas[0]
        sistema = chamada["messages"][0]["content"]
        self.assertTrue(chamada["stream"])
        self.assertEqual(chamada["options"]["temperature"], 0.8)
        self.assertIn("Lia. Maga Elfa, Nível 1", sistema)
        self.assertIn(prompts.ARCHETYPES["Roleplay"], sistema)
        self.assertRegex(sistema, r"<bandeja_de_dados>\nd20: ")
        self.assertEqual(len(chamada["messages"]), 12)  # sistema + 10 do histórico + a fala do Mestre
        self.assertEqual(chamada["messages"][-1]["content"], "Vocês entram na taverna.")

    def test_formato_errado_limpa_a_tela_e_usa_a_segunda_tentativa(self):
        falso = self.usar_ollama(OllamaFalso(
            responder=streams_em_sequencia(["Como assistente, ", "sugiro..."], [VALIDA])))
        resposta = jogador.run_player_simulator_turn_stream("x", "c", [], "Iniciante")
        partes = consumir(resposta)
        self.assertIn("", partes)  # o pedaço vazio avisa que a tela deve ser limpa
        self.assertEqual(resposta.texto, VALIDA)
        segunda = falso.chamadas[1]
        self.assertTrue(segunda["stream"])
        self.assertEqual(segunda["messages"][-1]["content"], jogador.LEMBRETE_FORMATO)
        self.assertEqual(segunda["messages"][-2]["content"], "Como assistente, sugiro...")
        self.assertLessEqual(segunda["options"]["temperature"], 0.4)

    def test_duas_tentativas_invalidas_mantem_a_primeira_sem_repetir(self):
        falso = self.usar_ollama(OllamaFalso(responder=streams_em_sequencia(["ruim 1"], ["ruim 2"])))
        resposta = jogador.run_player_simulator_turn_stream("x", "c", [], "Iniciante")
        consumir(resposta)
        self.assertEqual(resposta.texto, "ruim 1")
        self.assertEqual(len(falso.chamadas), 2)  # só uma segunda tentativa

    def test_falha_do_ollama_vira_ollama_error_ao_iterar(self):
        self.usar_ollama(OllamaFalso(falha=ConnectionError("fora")))
        resposta = jogador.run_player_simulator_turn_stream("x", "c", [], "Iniciante")  # montar o prompt não falha
        with self.assertRaises(OllamaError):
            consumir(resposta)

    def test_queda_no_meio_da_fala_guarda_o_texto_parcial(self):
        def gerar(kwargs):
            yield {"message": {"content": "par"}}
            raise ConnectionError("caiu")

        self.usar_ollama(OllamaFalso(responder=gerar))
        resposta = jogador.run_player_simulator_turn_stream("x", "c", [], "Iniciante")
        with self.assertRaises(OllamaError):
            consumir(resposta)
        self.assertEqual(resposta.texto, "par")


class FeedbackEmStreamTest(BaseTeste):
    LONGO = [{"role": "assistant", "content": "saudação"}, {"role": "user", "content": "Vocês entram na taverna."},
             {"role": "assistant", "content": VALIDA}, {"role": "user", "content": "Role Percepção CD 12."}]

    def test_feedback_chega_em_pedacos_com_o_historico_no_prompt(self):
        falso = self.usar_ollama(OllamaFalso(chunks=["**Pontos Fortes** ", "..."]))
        stream = jogador.iniciar_feedback_stream(self.LONGO)
        self.assertEqual(list(stream.tokens()), ["**Pontos Fortes** ", "..."])
        chamada = falso.chamadas[0]
        self.assertTrue(chamada["stream"])
        self.assertEqual(chamada["options"]["temperature"], 0.4)
        self.assertIn("Mestre (usuário): Vocês entram na taverna.", chamada["messages"][0]["content"])
        self.assertEqual(chamada["messages"][1]["role"], "user")

    def test_falha_do_ollama(self):
        self.usar_ollama(OllamaFalso(falha=ConnectionError("fora")))
        with self.assertRaises(OllamaError):
            jogador.iniciar_feedback_stream(self.LONGO)


if __name__ == "__main__":
    unittest.main()