import unittest

from rpgassistant.errors import OllamaError
from rpgassistant.modes import mestre
from tests.helpers import BaseTeste, OllamaFalso


def historico(n):
    return [{"role": "assistant" if i % 2 == 0 else "user", "content": f"m{i}"} for i in range(n)]


class ExtrairEstadoTest(unittest.TestCase):
    def test_extrai_e_remove_a_linha(self):
        texto, estado = mestre.extrair_estado("O goblin cai.\nO que você faz?\n[ESTADO] Jogador PV 12/15 | Goblin PV 0/7 CA 15", "antigo")
        self.assertEqual(texto, "O goblin cai.\nO que você faz?")
        self.assertEqual(estado, "Jogador PV 12/15 | Goblin PV 0/7 CA 15")

    def test_sem_combate_limpa_o_estado(self):
        texto, estado = mestre.extrair_estado("Você descansa.\n\n[ESTADO] Sem combate", "Jogador PV 3/15")
        self.assertEqual(estado, "")
        self.assertNotIn("[ESTADO]", texto)

    def test_sem_linha_mantem_o_estado_anterior(self):
        self.assertEqual(mestre.extrair_estado("Você anda pelo corredor.", "Jogador PV 3/15"),
                         ("Você anda pelo corredor.", "Jogador PV 3/15"))

    def test_varias_linhas_vale_a_ultima(self):
        texto, estado = mestre.extrair_estado("a\n[estado]: Jogador PV 1/10\nb\n[ESTADO] Jogador PV 2/10", "")
        self.assertEqual(estado, "Jogador PV 2/10")
        self.assertNotIn("[", texto)

    def test_marcador_no_meio_da_frase_nao_conta(self):
        self.assertEqual(mestre.extrair_estado("Ele grita [ESTADO] no meio da frase.", "x")[1], "x")


class OcultarLinhaEstadoTest(unittest.TestCase):
    def test_esconde_a_linha_completa_e_a_parcial(self):
        for texto in ("Ele ataca.\n[ESTADO] Jogador PV 3/10", "Ele ataca.\n[ESTA", "Ele ataca.\n[", "Ele ataca.\n[ESTADO",
                      "Ele ataca.\n\n  [estado]: x"):
            with self.subTest(texto=texto):
                self.assertEqual(mestre.ocultar_linha_estado(texto), "Ele ataca.")

    def test_nao_esconde_colchetes_comuns(self):
        for texto in ("veja [", "Texto normal", "[nota] importante"):
            with self.subTest(texto=texto):
                self.assertEqual(mestre.ocultar_linha_estado(texto), texto)

    def test_so_a_linha_de_estado_resulta_em_vazio(self):
        self.assertEqual(mestre.ocultar_linha_estado("[ESTADO] Sem combate"), "")


class MontarConsultaTest(unittest.TestCase):
    def test_acao_primeiro_e_fim_da_fala_do_mestre(self):
        hist = [{"role": "assistant", "content": "A" * 400 + " Faça um teste de Percepção CD 12."}, {"role": "user", "content": "x"}]
        consulta = mestre.montar_consulta("Tirei 14 no dado", hist)
        self.assertTrue(consulta.startswith("Tirei 14 no dado."))
        self.assertTrue(consulta.endswith("Faça um teste de Percepção CD 12."))
        self.assertLessEqual(len(consulta), len("Tirei 14 no dado") + 2 + 250)

    def test_sem_historico_so_a_acao(self):
        self.assertEqual(mestre.montar_consulta("Olho ao redor", []), "Olho ao redor.")


RESPOSTA_COMBATE = "O goblin ataca! Acerta 6 de dano.\nO que você faz?\n[ESTADO] Jogador PV 9/15 | Goblin PV 7/7 CA 15"


def rodar_turno(user_input, cenario, personagem, historico, estado=""):
    """Executa um turno e devolve (fala sem a linha de estado, fontes, novo estado), como o controlador faz."""
    stream, fontes = mestre.run_master_turn_stream(user_input, cenario, personagem, historico, estado)
    list(stream.tokens())
    texto, novo_estado = mestre.extrair_estado(stream.texto, estado)
    return texto, fontes, novo_estado


class RunMasterTurnStreamTest(BaseTeste):
    def test_monta_o_prompt_e_devolve_texto_fontes_e_estado(self):
        falso = self.usar_ollama(OllamaFalso(RESPOSTA_COMBATE))
        consultas = self.usar_busca("CTX-REGRAS", "Core | MM")
        texto, fontes, estado = rodar_turno(
            "Ataco o goblin", "Tumba", "Guerreiro", historico(30), "Jogador PV 15/15 | Goblin PV 7/7 CA 15")
        chamada = falso.chamadas[0]
        sistema = chamada["messages"][0]["content"]
        self.assertTrue(chamada["stream"])
        self.assertIn("Jogador PV 15/15 | Goblin PV 7/7 CA 15", sistema)
        self.assertRegex(sistema, r"<bandeja_de_dados>\nd20: ")
        self.assertIn("CTX-REGRAS", sistema)
        self.assertEqual(consultas[0][1], 3)
        self.assertEqual(chamada["options"]["temperature"], 0.7)
        self.assertEqual(len(chamada["messages"]), 1 + 10 + 1)
        self.assertEqual(chamada["messages"][1]["content"], "m0")
        self.assertEqual(chamada["messages"][-1]["content"], "Ataco o goblin")
        self.assertEqual(texto, "O goblin ataca! Acerta 6 de dano.\nO que você faz?")
        self.assertEqual((fontes, estado), ("Core | MM", "Jogador PV 9/15 | Goblin PV 7/7 CA 15"))

    def test_sem_estado_avisa_que_nao_ha_combate(self):
        falso = self.usar_ollama(OllamaFalso("Você vê um corredor."))
        self.usar_busca()
        rodar_turno("Abro a porta", "Tumba", "Guerreiro", [], "")
        self.assertIn("Sem combate em andamento.", falso.chamadas[0]["messages"][0]["content"])

    def test_so_role_e_content_seguem_ao_modelo(self):
        falso = self.usar_ollama(OllamaFalso("ok"))
        self.usar_busca()
        rodar_turno("ok", "T", "C", [{"role": "assistant", "content": "abertura", "estado": "X"},
                                      {"role": "user", "content": "oi"}], "")
        self.assertTrue(all(set(m) == {"role", "content"} for m in falso.chamadas[0]["messages"]))

    def test_falha_do_ollama(self):
        self.usar_ollama(OllamaFalso(falha=ConnectionError("fora")))
        self.usar_busca()
        with self.assertRaises(OllamaError):
            mestre.run_master_turn_stream("x", "T", "C", [], "")

    def test_estado_vindo_do_stream(self):
        self.usar_ollama(OllamaFalso(chunks=["O goblin ataca.\n", "[ESTADO] Jogador PV 5/10"]))
        self.usar_busca("CTX2", "Core | MM")
        stream, fontes = mestre.run_master_turn_stream("Ataco", "Tumba", "Guerreiro", [], "")
        list(stream.tokens())
        self.assertEqual(fontes, "Core | MM")
        self.assertEqual(mestre.extrair_estado(stream.texto, ""), ("O goblin ataca.", "Jogador PV 5/10"))


if __name__ == "__main__":
    unittest.main()