import unittest

from rpgassistant.core.historico import janela_historico


def historico(n: int) -> list:
    return [{"role": "assistant" if i % 2 == 0 else "user", "content": f"m{i}"} for i in range(n)]


class JanelaHistoricoTest(unittest.TestCase):
    def test_historico_curto_passa_inteiro(self):
        self.assertEqual(janela_historico(historico(4), 10), historico(4))

    def test_preserva_a_abertura_e_limita_o_tamanho(self):
        janela = janela_historico(historico(30), 10)
        self.assertEqual(janela[0]["content"], "m0")
        self.assertEqual(len(janela), 10)
        self.assertEqual(janela[-1]["content"], "m29")

    def test_mantem_a_alternancia_de_papeis(self):
        janela = janela_historico(historico(30), 10)
        self.assertTrue(all(janela[i]["role"] != janela[i + 1]["role"] for i in range(len(janela) - 1)))

    def test_tamanhos_extremos(self):
        h = historico(30)
        self.assertEqual(janela_historico(h, 1), [h[-1]])
        self.assertEqual(janela_historico(h, 0), [])

    def test_nao_altera_a_lista_original(self):
        h = historico(30)
        janela_historico(h, 10)
        self.assertEqual(len(h), 30)


if __name__ == "__main__":
    unittest.main()