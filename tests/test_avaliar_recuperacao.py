"""
Testes da avaliação da busca (rpgassistant/avaliar_recuperacao.py) e da função de busca que ela usa
(rag.buscar_trechos). A avaliação de verdade precisa dos seus livros indexados; aqui a busca é trocada por uma falsa.
"""

import contextlib
import io
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from rpgassistant import avaliar_recuperacao as av
from rpgassistant.avaliar_recuperacao import Pergunta
from rpgassistant.errors import BaseVaziaError
from rpgassistant.services import rag
from rpgassistant.services.rag import Trecho
from tests.helpers import BaseTeste


def trecho(texto, fonte="Core | Player's Handbook", similaridade=0.5):
    return Trecho(texto, fonte, similaridade)


class TrechoConfereTest(unittest.TestCase):
    def test_ignora_maiusculas_acentos_e_quebras_de_linha(self):
        pergunta = Pergunta("x", ("at least 8 hours", "Fúria"))
        self.assertTrue(av.trecho_confere(trecho("A Long Rest lasts at\nleast   8 hours."), pergunta))
        self.assertTrue(av.trecho_confere(trecho("A FURIA do bárbaro"), pergunta))

    def test_so_conta_palavra_inteira(self):
        pergunta = Pergunta("x", ("Rage",))
        self.assertFalse(av.trecho_confere(trecho("The average damage of a courage check"), pergunta))
        self.assertTrue(av.trecho_confere(trecho("Barbarian Rage feature"), pergunta))

    def test_sem_nenhum_termo_nao_confere(self):
        self.assertFalse(av.trecho_confere(trecho("Texto sem relação"), Pergunta("x", ("Grappled", "Agarrado"))))

    def test_livro_opcional(self):
        pergunta = Pergunta("x", ("rage",), "Player")
        self.assertTrue(av.trecho_confere(trecho("Rage", fonte="Core | Player's Handbook - pág. 3"), pergunta))
        self.assertFalse(av.trecho_confere(trecho("Rage", fonte="Suplemento | Xanathar's Guide"), pergunta))


class LerPerguntasTest(unittest.TestCase):
    def ler(self, conteudo):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "perguntas.txt"
            arquivo.write_text(conteudo, encoding="utf-8")
            return av.ler_perguntas(arquivo)

    def test_formato_com_comentarios_e_livro_opcional(self):
        perguntas = self.ler("# comentário\n\nComo funciona agarrar? | Grappled ; Agarrado\n"
                             "Descanso longo? | at least 8 hours | Player's Handbook\n")
        self.assertEqual(perguntas, [
            Pergunta("Como funciona agarrar?", ("Grappled", "Agarrado")),
            Pergunta("Descanso longo?", ("at least 8 hours",), "Player's Handbook"),
        ])

    def test_linha_sem_barra_diz_a_linha(self):
        with self.assertRaisesRegex(ValueError, "Linha 2"):
            self.ler("Boa | termo\nsó a pergunta\n")

    def test_linha_sem_termos_diz_a_linha(self):
        with self.assertRaisesRegex(ValueError, "Linha 1"):
            self.ler("Pergunta | ;  ; \n")

    def test_arquivo_sem_perguntas(self):
        with self.assertRaisesRegex(ValueError, "nenhuma pergunta"):
            self.ler("# só comentário\n\n")


class AvaliarTest(unittest.TestCase):
    PERGUNTA = Pergunta("Como funciona agarrar?", ("Grappled",))

    def test_posicao_do_primeiro_acerto_e_melhor_similaridade(self):
        trechos = [trecho("outro assunto", similaridade=0.7), trecho("Grappled: speed is 0", similaridade=0.6),
                   trecho("Grappled de novo", similaridade=0.4)]
        chamadas = []
        buscar = lambda texto, k: chamadas.append((texto, k)) or trechos
        [resultado] = av.avaliar([self.PERGUNTA], 3, buscar)
        self.assertEqual(resultado.posicao, 2)
        self.assertEqual(resultado.melhor_similaridade, 0.7)
        self.assertEqual(chamadas, [("Como funciona agarrar?", 3)])

    def test_pergunta_sem_acerto(self):
        trechos = [trecho("outro assunto", similaridade=0.3)]
        [resultado] = av.avaliar([self.PERGUNTA], 3, lambda texto, k: trechos)
        self.assertIsNone(resultado.posicao)
        self.assertEqual(resultado.primeiro_trecho, trechos[0])

    def test_busca_sem_trechos(self):
        [resultado] = av.avaliar([self.PERGUNTA], 3, lambda texto, k: [])
        self.assertEqual((resultado.posicao, resultado.melhor_similaridade, resultado.primeiro_trecho), (None, None, None))


class ResumirTest(unittest.TestCase):
    def resultados(self, *posicoes):
        return [av.Resultado(Pergunta(f"p{i}", ("x",)), posicao, 0.5, None) for i, posicao in enumerate(posicoes)]

    def test_contagens_e_mrr(self):
        resumo = av.resumir(self.resultados(1, 3, None, 2), k=5)
        self.assertEqual((resumo.total, resumo.k), (4, 5))
        self.assertEqual((resumo.acertos_em_1, resumo.acertos_em_3, resumo.acertos_em_k), (1, 3, 3))
        self.assertAlmostEqual(resumo.mrr, (1 + 1 / 3 + 0 + 1 / 2) / 4)

    def test_acerto_depois_do_terceiro_so_conta_em_k(self):
        resumo = av.resumir(self.resultados(4), k=5)
        self.assertEqual((resumo.acertos_em_1, resumo.acertos_em_3, resumo.acertos_em_k), (0, 0, 1))

    def test_sem_perguntas(self):
        resumo = av.resumir([], k=5)
        self.assertEqual((resumo.total, resumo.mrr), (0, 0.0))


class PerguntasDeExemploTest(unittest.TestCase):
    def test_estao_bem_formadas(self):
        textos = [p.texto for p in av.PERGUNTAS_DE_EXEMPLO]
        self.assertEqual(len(textos), len(set(textos)))  # sem repetidas
        for pergunta in av.PERGUNTAS_DE_EXEMPLO:
            with self.subTest(pergunta=pergunta.texto):
                self.assertTrue(pergunta.termos)
                self.assertTrue(all(termo.strip() for termo in pergunta.termos))


class MainTest(BaseTeste):
    def executar(self, argv):
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            codigo = av.main(argv)
        return codigo, saida.getvalue()

    def test_sem_base_explica_e_retorna_erro(self):
        def sem_base(texto, k):
            raise BaseVaziaError("A base de livros ainda não foi indexada. Rode: python -m rpgassistant.indexar")

        with mock.patch.object(av.rag, "buscar_trechos", sem_base):
            codigo, saida = self.executar([])
        self.assertEqual(codigo, 1)
        self.assertIn("rpgassistant.indexar", saida)

    def test_relatorio_com_todos_os_acertos(self):
        por_texto = {p.texto: p for p in av.PERGUNTAS_DE_EXEMPLO}
        buscar = lambda texto, k: [trecho(" ".join(por_texto[texto].termos), similaridade=0.7)]
        with mock.patch.object(av.rag, "buscar_trechos", buscar):
            codigo, saida = self.executar([])
        total = len(av.PERGUNTAS_DE_EXEMPLO)
        self.assertEqual(codigo, 0)
        self.assertIn(f"{total} de {total} (100%)", saida)
        self.assertIn("MRR", saida)
        self.assertNotIn("PERGUNTAS SEM ACERTO", saida)

    def test_relatorio_mostra_o_que_falhou(self):
        buscar = lambda texto, k: [trecho("Um texto sobre outro assunto", fonte="Core | PHB - pág. 7", similaridade=0.31)]
        with mock.patch.object(av.rag, "buscar_trechos", buscar):
            codigo, saida = self.executar([])
        self.assertEqual(codigo, 0)
        self.assertIn("PERGUNTAS SEM ACERTO", saida)
        self.assertIn("termos esperados: Grappled ; Agarrado", saida)
        self.assertIn("Core | PHB - pág. 7 (0.31)", saida)

    def test_arquivo_invalido_retorna_erro_com_a_linha(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "ruim.txt"
            arquivo.write_text("pergunta sem barra\n", encoding="utf-8")
            codigo, saida = self.executar(["--perguntas", str(arquivo)])
        self.assertEqual(codigo, 1)
        self.assertIn("Linha 1", saida)

    def test_k_invalido(self):
        codigo, saida = self.executar(["--k", "0"])
        self.assertEqual(codigo, 1)
        self.assertIn("--k", saida)


class Doc:
    """Trecho de livro de mentira: só o que a busca lê."""

    def __init__(self, page_content, metadata):
        self.page_content, self.metadata = page_content, metadata


class BancoFalso:
    """Base vetorial de mentira: devolve (documento, distância), do mais próximo para o mais distante."""

    def __init__(self, pares):
        self.pares = pares
        self.ultima = None
        self._collection = types.SimpleNamespace(metadata=None)

    def similarity_search_with_score(self, query, k):
        self.ultima = (query, k)
        return self.pares


class BuscarTrechosTest(BaseTeste):
    def test_devolve_os_trechos_em_ordem_com_fonte_pagina_e_similaridade(self):
        banco = BancoFalso([
            (Doc("  texto A  ", {"source": "/x/rulebooks/core/PHB.pdf", "page": 0}), 0.6),
            (Doc("texto B", {"source": "/x/rulebooks/suplements/Tasha.md"}), 1.2),
        ])
        with mock.patch.object(rag, "_vector_store", banco):
            trechos = rag.buscar_trechos("agarrar", k=2)
        self.assertEqual([t.texto for t in trechos], ["texto A", "texto B"])  # o texto vem sem espaços nas pontas
        self.assertEqual([t.fonte for t in trechos], ["Core | PHB - pág. 1", "Suplemento | Tasha"])
        self.assertAlmostEqual(trechos[0].similaridade, 1 - 0.36 / 2)
        self.assertAlmostEqual(trechos[1].similaridade, 1 - 1.44 / 2)
        self.assertEqual(banco.ultima, ("agarrar", 2))

    def test_k_padrao_vem_da_configuracao(self):
        banco = BancoFalso([(Doc("A", {"source": "/x/rulebooks/core/PHB.md"}), 0.5)])
        with mock.patch.object(rag, "_vector_store", banco):
            rag.buscar_trechos("agarrar")
        self.assertEqual(banco.ultima[1], self.cfg.top_k_assistente)

    def test_sem_resultados_devolve_lista_vazia(self):
        with mock.patch.object(rag, "_vector_store", BancoFalso([])):
            self.assertEqual(rag.buscar_trechos("x"), [])

    def test_sem_base_levanta_erro_com_instrucao(self):
        with mock.patch.object(rag, "_vector_store", None):
            with self.assertRaisesRegex(BaseVaziaError, "rpgassistant.indexar"):
                rag.buscar_trechos("x")


if __name__ == "__main__":
    unittest.main()