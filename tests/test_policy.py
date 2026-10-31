import unittest

from rpgassistant.core import policy
from rpgassistant.services import prompts


class RelevanciaTest(unittest.TestCase):
    def test_avaliar_relevancia(self):
        self.assertTrue(policy.avaliar_relevancia(0.5, 0.3))
        self.assertTrue(policy.avaliar_relevancia(0.3, 0.3))   # no limite, passa
        self.assertFalse(policy.avaliar_relevancia(0.29, 0.3))
        self.assertFalse(policy.avaliar_relevancia(None, 0.0))  # sem trechos nunca passa
        self.assertTrue(policy.avaliar_relevancia(-0.2, 0.0) is False)
        self.assertTrue(policy.avaliar_relevancia(0.0, 0.0))    # limiar 0 desliga a barreira

    def test_motivo_da_recusa(self):
        self.assertIn("0.12", policy.motivo_da_recusa(0.12, 0.3))
        self.assertIn("0.30", policy.motivo_da_recusa(0.12, 0.3))
        self.assertIn("nenhum trecho", policy.motivo_da_recusa(None, 0.3))


class SentinelaTest(unittest.TestCase):
    def test_reconhece_a_recusa_do_modelo(self):
        for texto in ("NAO_ENCONTRADO", "  NAO_ENCONTRADO.  ", "NÃO_ENCONTRADO", "nao encontrado", "Não-encontrado",
                      "NAO_ENCONTRADO\nSinto muito."):
            with self.subTest(texto=texto):
                self.assertTrue(policy.eh_recusa_do_modelo(texto))

    def test_respostas_normais_nao_sao_recusa(self):
        for texto in ("Agarrado [Grappled] reduz a velocidade a 0.", "Não encontrei muitos detalhes, mas...", "", "NAO"):
            with self.subTest(texto=texto):
                self.assertFalse(policy.eh_recusa_do_modelo(texto))

    def test_texto_visivel_esconde_a_sentinela_mesmo_pela_metade(self):
        for parcial in ("N", "NAO", "NAO_", "NAO_ENC", "NAO_ENCONTRADO", "NAO_ENCONTRADO. Sinto muito", "Não", "  NAO_EN"):
            with self.subTest(parcial=parcial):
                self.assertEqual(policy.texto_visivel(parcial), "")

    def test_texto_visivel_mostra_o_resto(self):
        for texto in ("Agarrado reduz a velocidade.", "Não consigo explicar isso agora.", "NAO_CONSIGO", "Na verdade, sim"):
            with self.subTest(texto=texto):
                self.assertEqual(policy.texto_visivel(texto), texto)

    def test_a_sentinela_do_codigo_esta_no_prompt(self):
        self.assertIn(policy.SENTINELA, prompts.LIVROS_PROMPT)

    def test_recusa_padrao(self):
        self.assertIn("não encontrei", policy.RECUSA)


if __name__ == "__main__":
    unittest.main()