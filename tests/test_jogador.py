import unittest

from rpgassistant.errors import OllamaError
from rpgassistant.modes import jogador
from rpgassistant.services import prompts
from tests.helpers import BaseTeste, OllamaFalso, resposta

VALIDA = '[Ação]: Lia se afasta.\n[Fala]: "Mestre, posso rolar Percepção?"'


def historico(n):
    return [{"role": "assistant" if i % 2 == 0 else "user", "content": f"m{i}"} for i in range(n)]


def respostas_em_sequencia(*textos):
    fila = iter(textos)
    return lambda kwargs: resposta(next(fila))


class FormatoTest(unittest.TestCase):
    def test_formato_valido(self):
        for texto in (VALIDA, "[ação]: x\n[fala]: y", "[Acao]: x\n[FALA]: y"):
            with self.subTest(texto=texto):
                self.assertTrue(jogador.formato_valido(texto))

    def test_formato_invalido(self):
        for texto in ("Lia se afasta e diz oi.", "[Ação]: só ação"):
            with self.subTest(texto=texto):
                self.assertFalse(jogador.formato_valido(texto))


class PerfilTest(unittest.TestCase):
    def test_bloco_do_arquetipo(self):
        self.assertEqual(jogador.bloco_arquetipo("Tático"), prompts.ARCHETYPES["Tático"])
        self.assertEqual(jogador.bloco_arquetipo("Personalizado", "  muito desconfiado  "), "muito desconfiado")
        self.assertEqual(jogador.bloco_arquetipo("Personalizado", "  "), jogador.PERFIL_NEUTRO)
        self.assertEqual(jogador.bloco_arquetipo("Inexistente"), jogador.PERFIL_NEUTRO)

    def test_saudacao_usa_o_nome(self):
        self.assertIn("Lia", jogador.saudacao_inicial("Lia", "Iniciante"))
        self.assertIn("Lia", jogador.saudacao_inicial("Lia", "Qualquer"))

    def test_o_modo_nao_consulta_os_livros(self):
        self.assertFalse(hasattr(jogador, "recuperar_contexto"))
        self.assertFalse(hasattr(jogador, "rag"))


class TurnoTest(BaseTeste):
    def test_resposta_valida_faz_uma_chamada_com_ficha_perfil_e_dados(self):
        falso = self.usar_ollama(OllamaFalso(VALIDA))
        resp = jogador.run_player_simulator_turn("Vocês entram na taverna.", "Lia. Maga Elfa, Nível 1", historico(30), "Roleplay")
        sistema = falso.chamadas[0]["messages"][0]["content"]
        self.assertEqual((resp, len(falso.chamadas)), (VALIDA, 1))
        self.assertIn("Lia. Maga Elfa, Nível 1", sistema)
        self.assertIn(prompts.ARCHETYPES["Roleplay"], sistema)
        self.assertRegex(sistema, r"<bandeja_de_dados>\nd20: ")
        self.assertEqual(falso.chamadas[0]["options"]["temperature"], 0.8)
        mensagens = falso.chamadas[0]["messages"]
        self.assertEqual(len(mensagens), 12)
        self.assertEqual((mensagens[1]["content"], mensagens[-1]["content"]), ("m0", "Vocês entram na taverna."))

    def test_temperatura_por_perfil(self):
        for perfil, esperado in (("Iniciante", 0.5), ("Tático", 0.3), ("Personalizado", 0.6), ("Outro", 0.5)):
            with self.subTest(perfil=perfil):
                falso = self.usar_ollama(OllamaFalso(VALIDA))
                jogador.run_player_simulator_turn("x", "c", [], perfil, "perfil")
                self.assertEqual(falso.chamadas[0]["options"]["temperature"], esperado)

    def test_trocar_de_perfil_muda_so_o_prompt_do_sistema(self):
        falso = self.usar_ollama(OllamaFalso(VALIDA))
        jogador.run_player_simulator_turn("x", "c", historico(6), "Iniciante")
        jogador.run_player_simulator_turn("x", "c", historico(6), "Tático")
        primeira, segunda = (c["messages"] for c in falso.chamadas)
        self.assertIn(prompts.ARCHETYPES["Iniciante"], primeira[0]["content"])
        self.assertIn(prompts.ARCHETYPES["Tático"], segunda[0]["content"])
        self.assertEqual(primeira[1:], segunda[1:])

    def test_formato_errado_pede_de_novo_e_usa_a_segunda(self):
        falso = self.usar_ollama(OllamaFalso(responder=respostas_em_sequencia("Como assistente, sugiro...", VALIDA)))
        resp = jogador.run_player_simulator_turn("x", "c", [], "Iniciante")
        self.assertEqual(resp, VALIDA)
        segunda = falso.chamadas[1]
        self.assertEqual(segunda["messages"][-1]["content"], jogador.LEMBRETE_FORMATO)
        self.assertEqual(segunda["messages"][-2]["content"], "Como assistente, sugiro...")
        self.assertLessEqual(segunda["options"]["temperature"], 0.4)

    def test_duas_respostas_invalidas_mantem_a_primeira_sem_repetir(self):
        falso = self.usar_ollama(OllamaFalso(responder=respostas_em_sequencia("ruim 1", "ruim 2")))
        self.assertEqual(jogador.run_player_simulator_turn("x", "c", [], "Iniciante"), "ruim 1")
        self.assertEqual(len(falso.chamadas), 2)

    def test_falha_do_ollama(self):
        self.usar_ollama(OllamaFalso(falha=ConnectionError("fora")))
        with self.assertRaises(OllamaError):
            jogador.run_player_simulator_turn("x", "c", [], "Iniciante")


class FeedbackTest(BaseTeste):
    CURTO = [{"role": "assistant", "content": "oi"}, {"role": "user", "content": "cena"}]
    LONGO = [{"role": "assistant", "content": "saudação"}, {"role": "user", "content": "Vocês entram na taverna."},
             {"role": "assistant", "content": VALIDA}, {"role": "user", "content": "Role Percepção CD 12."}]

    def test_historico_curto_avisa_sem_chamar_o_modelo(self):
        falso = self.usar_ollama(OllamaFalso())
        self.assertFalse(jogador.historico_suficiente(self.CURTO))
        self.assertEqual(jogador.gerar_feedback(self.CURTO), jogador.AVISO_HISTORICO_CURTO)
        self.assertEqual(falso.chamadas, [])

    def test_duas_falas_do_mestre_bastam(self):
        self.assertTrue(jogador.historico_suficiente(self.LONGO))

    def test_gera_o_feedback_com_o_historico_formatado(self):
        falso = self.usar_ollama(OllamaFalso("**Pontos Fortes** ...\n"))
        self.assertEqual(jogador.gerar_feedback(self.LONGO), "**Pontos Fortes** ...")
        chamada = falso.chamadas[0]
        sistema = chamada["messages"][0]["content"]
        self.assertEqual(chamada["options"]["temperature"], 0.4)
        self.assertIn("Mestre (usuário): Vocês entram na taverna.", sistema)
        self.assertIn("Jogador (IA): [Ação]: Lia se afasta.", sistema)
        self.assertEqual(chamada["messages"][1]["role"], "user")

    def test_historico_enorme_e_cortado_pelo_inicio(self):
        enorme = [{"role": "user" if i % 2 else "assistant", "content": "z" * 1000 + str(i)} for i in range(40)]
        texto = jogador.formatar_historico(enorme)
        self.assertTrue(texto.startswith("[início da sessão omitido]"))
        self.assertLessEqual(len(texto), jogador.LIMITE_HISTORICO_FEEDBACK + 40)
        self.assertTrue(texto.endswith("39"))


if __name__ == "__main__":
    unittest.main()