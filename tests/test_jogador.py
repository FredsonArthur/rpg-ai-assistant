"""
Testes do modo Jogador (rpgassistant/modes/jogador.py): formato, perfis e histórico do feedback.
A fala e o feedback em streaming são testados em tests/test_jogador_stream.py.
"""

import unittest

from rpgassistant.modes import jogador
from rpgassistant.services import prompts
from tests.helpers import VALIDA, BaseTeste, OllamaFalso


def historico(n):
    """Histórico de `n` mensagens alternando assistente e usuário, como o do chat."""
    return [{"role": "assistant" if i % 2 == 0 else "user", "content": f"m{i}"} for i in range(n)]


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


class PerfilNoTurnoTest(BaseTeste):
    """Como o perfil escolhido muda a chamada ao modelo."""

    def test_temperatura_por_perfil(self):
        for perfil, esperado in (("Iniciante", 0.5), ("Tático", 0.3), ("Personalizado", 0.6), ("Outro", 0.5)):
            with self.subTest(perfil=perfil):
                falso = self.usar_ollama(OllamaFalso(VALIDA))
                resposta = jogador.run_player_simulator_turn_stream("x", "c", [], perfil, "perfil")
                list(resposta.tokens())
                self.assertEqual(falso.chamadas[0]["options"]["temperature"], esperado)

    def test_trocar_de_perfil_muda_so_o_prompt_do_sistema(self):
        falso = self.usar_ollama(OllamaFalso(VALIDA))
        for perfil in ("Iniciante", "Tático"):
            list(jogador.run_player_simulator_turn_stream("x", "c", historico(6), perfil).tokens())
        primeira, segunda = (c["messages"] for c in falso.chamadas)
        self.assertIn(prompts.ARCHETYPES["Iniciante"], primeira[0]["content"])
        self.assertIn(prompts.ARCHETYPES["Tático"], segunda[0]["content"])
        self.assertEqual(primeira[1:], segunda[1:])  # o histórico e a fala do Mestre são os mesmos


class HistoricoDoFeedbackTest(unittest.TestCase):
    CURTO = [{"role": "assistant", "content": "oi"}, {"role": "user", "content": "cena"}]
    LONGO = [{"role": "assistant", "content": "saudação"}, {"role": "user", "content": "Vocês entram na taverna."},
             {"role": "assistant", "content": VALIDA}, {"role": "user", "content": "Role Percepção CD 12."}]

    def test_historico_curto_nao_basta(self):
        self.assertFalse(jogador.historico_suficiente(self.CURTO))

    def test_duas_falas_do_mestre_bastam(self):
        self.assertTrue(jogador.historico_suficiente(self.LONGO))

    def test_formata_quem_falou_cada_trecho(self):
        texto = jogador.formatar_historico(self.LONGO)
        self.assertIn("Mestre (usuário): Vocês entram na taverna.", texto)
        self.assertIn("Jogador (IA): [Ação]: Lia olha ao redor.", texto)

    def test_historico_enorme_e_cortado_pelo_inicio(self):
        enorme = [{"role": "user" if i % 2 else "assistant", "content": "z" * 1000 + str(i)} for i in range(40)]
        texto = jogador.formatar_historico(enorme)
        self.assertTrue(texto.startswith("[início da sessão omitido]"))
        self.assertLessEqual(len(texto), jogador.LIMITE_HISTORICO_FEEDBACK + 40)
        self.assertTrue(texto.endswith("39"))


if __name__ == "__main__":
    unittest.main()