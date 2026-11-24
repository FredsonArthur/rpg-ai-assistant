"""
Filtro de trechos sem texto na indexação (rpgassistant/services/rag.py)
-----------------------------------------------------------------------
Linhas de tabela, separadores e títulos soltos do Markdown viravam trechos como "|", que chegavam a ser o
melhor resultado de uma busca (similaridade 0.66 para "Concentration"). Eles não devem ser indexados.
"""

import unittest

from rpgassistant.services import rag


class Doc:
    """Trecho de livro de mentira: só o que o filtro lê."""

    def __init__(self, page_content):
        self.page_content = page_content


class TrechoTemTextoTest(unittest.TestCase):
    def test_so_formatacao_nao_tem_texto(self):
        for texto in ("|", "___", "> >", "---", "####", "| | |", "|---|---|", "\n \n", ""):
            with self.subTest(texto=texto):
                self.assertFalse(rag.trecho_tem_texto(Doc(texto)))

    def test_titulo_solto_muito_curto_nao_tem_texto(self):
        self.assertFalse(rag.trecho_tem_texto(Doc("#### Added Benefit")))  # 15 letras

    def test_frase_curta_tem_texto(self):
        """Caso real: uma frase de uma linha vale a pena e não pode ser descartada."""
        self.assertTrue(rag.trecho_tem_texto(Doc("***Undead Nature.*** A deathlock doesn't require air, food, drink, or sleep.")))

    def test_paragrafo_normal_tem_texto(self):
        self.assertTrue(rag.trecho_tem_texto(Doc("Whenever you start your turn with 0 Hit Points, you must make a Death Saving Throw. " * 3)))

    def test_conta_letras_com_acento(self):
        self.assertTrue(rag.trecho_tem_texto(Doc("ação ação ação ação ação ação")))  # 24 letras acentuadas

    def test_o_limite_e_o_documentado(self):
        self.assertEqual(rag.MIN_LETRAS_POR_TRECHO, 20)
        self.assertFalse(rag.trecho_tem_texto(Doc("a" * 19)))
        self.assertTrue(rag.trecho_tem_texto(Doc("a" * 20)))


class DescartarTrechosSemTextoTest(unittest.TestCase):
    def test_separa_e_conta(self):
        bons = [Doc("A creature that is Grappled has a Speed of 0 and cannot benefit from any bonus to its Speed."),
                Doc("Whenever you start your turn with 0 Hit Points, you must make a Death Saving Throw.")]
        lixo = [Doc("|"), Doc("___"), Doc("> >")]
        mantidos, descartados = rag.descartar_trechos_sem_texto([lixo[0], bons[0], lixo[1], bons[1], lixo[2]])
        self.assertEqual(mantidos, bons)  # a ordem dos trechos que ficam é mantida
        self.assertEqual(descartados, 3)

    def test_lista_vazia(self):
        self.assertEqual(rag.descartar_trechos_sem_texto([]), ([], 0))

    def test_so_lixo(self):
        self.assertEqual(rag.descartar_trechos_sem_texto([Doc("|"), Doc("---")]), ([], 2))


if __name__ == "__main__":
    unittest.main()