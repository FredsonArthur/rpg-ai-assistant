import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from rpgassistant import calibrar
from rpgassistant.errors import BaseVaziaError
from rpgassistant.services.rag import ResultadoBusca
from tests.helpers import BaseTeste


class SugerirLimiarTest(unittest.TestCase):
    def test_grupos_separados_sugere_um_valor_entre_eles(self):
        s = calibrar.sugerir_limiar([0.5, 0.6, 0.7], [0.1, 0.2, 0.3])
        self.assertTrue(s.separavel)
        self.assertEqual((s.acertos, s.total), (6, 6))
        self.assertGreater(s.limiar, 0.3)
        self.assertLessEqual(s.limiar, 0.5)
        self.assertEqual((s.minimo_dentro, s.maximo_fora), (0.5, 0.3))

    def test_grupos_sobrepostos_erra_o_minimo(self):
        s = calibrar.sugerir_limiar([0.2, 0.6, 0.7, 0.8], [0.3, 0.1, 0.15])
        self.assertFalse(s.separavel)
        self.assertEqual((s.acertos, s.total), (6, 7))  # só a pergunta de dentro com 0.2 fica de fora
        self.assertGreater(s.limiar, 0.3)

    def test_precisa_dos_dois_grupos(self):
        with self.assertRaises(ValueError):
            calibrar.sugerir_limiar([], [0.1])
        with self.assertRaises(ValueError):
            calibrar.sugerir_limiar([0.5], [])

    def test_ler_perguntas_ignora_linhas_vazias_e_comentarios(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "perguntas.txt"
            arquivo.write_text("# comentário\n\nComo funciona agarrar?\n  Qual o dano de queda?  \n", encoding="utf-8")
            self.assertEqual(calibrar.ler_perguntas(arquivo), ["Como funciona agarrar?", "Qual o dano de queda?"])


class CalibrarTest(BaseTeste):
    def executar(self, buscar, dentro, fora):
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            sugestao = calibrar.calibrar(dentro, fora, buscar=buscar)
        return sugestao, saida.getvalue()

    def test_relatorio_e_sugestao(self):
        notas = {"d1": 0.6, "d2": 0.55, "f1": 0.1, "f2": 0.2}
        buscar = lambda pergunta: ResultadoBusca("", "", notas[pergunta], 1)
        sugestao, texto = self.executar(buscar, ["d1", "d2"], ["f1", "f2"])
        self.assertTrue(sugestao.separavel)
        self.assertIn("Limiar atual: 0.30", texto)
        self.assertIn("passa", texto)
        self.assertIn("recusa", texto)
        self.assertIn(f"RPG_RELEVANCIA_MINIMA={sugestao.limiar:.2f}", texto)

    def test_pergunta_sem_trechos_conta_como_zero(self):
        buscar = lambda pergunta: ResultadoBusca("", "", None if pergunta == "f1" else 0.5, 0)
        sugestao, _ = self.executar(buscar, ["d1"], ["f1"])
        self.assertEqual(sugestao.maximo_fora, 0.0)

    def test_main_sem_base_explica_e_retorna_erro(self):
        from unittest import mock

        def sem_base(pergunta):
            raise BaseVaziaError("A base de livros ainda não foi indexada. Rode: python -m rpgassistant.indexar")

        saida = io.StringIO()
        with mock.patch.object(calibrar.rag, "buscar_contexto", sem_base), contextlib.redirect_stdout(saida):
            codigo = calibrar.main([])
        self.assertEqual(codigo, 1)
        self.assertIn("rpgassistant.indexar", saida.getvalue())


if __name__ == "__main__":
    unittest.main()