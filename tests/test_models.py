import unittest

from rpgassistant.core import models


class TituloTest(unittest.TestCase):
    def test_limpa_espacos(self):
        self.assertEqual(models.titulo_valido("  Como   funciona\n agarrar?  "), "Como funciona agarrar?")

    def test_vazio_levanta_erro(self):
        for texto in ("", "   ", "\n\t"):
            with self.subTest(texto=texto):
                with self.assertRaises(ValueError):
                    models.titulo_valido(texto)

    def test_trunca_com_reticencias(self):
        titulo = models.titulo_valido("a" * 200)
        self.assertEqual(len(titulo), models.LIMITE_TITULO)
        self.assertTrue(titulo.endswith("…"))

    def test_titulo_no_limite_nao_e_alterado(self):
        texto = "b" * models.LIMITE_TITULO
        self.assertEqual(models.titulo_valido(texto), texto)

    def test_gerar_titulo_usa_o_padrao_se_vazio(self):
        self.assertEqual(models.gerar_titulo("   "), models.TITULO_PADRAO)
        self.assertEqual(models.gerar_titulo("Como funciona agarrar?"), "Como funciona agarrar?")


if __name__ == "__main__":
    unittest.main()