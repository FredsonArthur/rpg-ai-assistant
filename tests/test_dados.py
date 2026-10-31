import random
import unittest

from rpgassistant.services import dados


class BandejaDeDadosTest(unittest.TestCase):
    def analisar(self, bandeja: str) -> dict:
        return {parte.split(": ")[0]: [int(x) for x in parte.split(": ")[1].split(", ")] for parte in bandeja.split(" | ")}

    def test_quantidade_de_cada_dado(self):
        valores = self.analisar(dados.bandeja_de_dados(random.Random(1)))
        self.assertEqual({k: len(v) for k, v in valores.items()},
                         {"d20": 4, "d12": 2, "d10": 2, "d8": 3, "d6": 4, "d4": 2})

    def test_valores_dentro_das_faces(self):
        for semente in range(50):
            for dado, valores in self.analisar(dados.bandeja_de_dados(random.Random(semente))).items():
                self.assertTrue(all(1 <= v <= int(dado[1:]) for v in valores), (dado, valores))

    def test_reprodutivel_com_a_mesma_semente(self):
        self.assertEqual(dados.bandeja_de_dados(random.Random(7)), dados.bandeja_de_dados(random.Random(7)))

    def test_d20_cobre_todos_os_valores(self):
        rng = random.Random(3)
        vistos = {v for _ in range(300) for v in self.analisar(dados.bandeja_de_dados(rng))["d20"]}
        self.assertEqual(vistos, set(range(1, 21)))

    def test_funciona_sem_semente(self):
        self.assertIn("d20: ", dados.bandeja_de_dados())


if __name__ == "__main__":
    unittest.main()