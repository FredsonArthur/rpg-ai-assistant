import math
import types
import unittest
from unittest import mock

from rpgassistant.errors import BaseVaziaError

from rpgassistant.services import rag
from tests.helpers import BaseTeste, OllamaFalso, resposta


class Doc:
    def __init__(self, page_content, metadata):
        self.page_content, self.metadata = page_content, metadata


class BancoFalso:
    """Banco que devolve (documento, distância), do mais próximo para o mais distante, como o Chroma."""

    def __init__(self, docs, distancias=None, espaco=None):
        self.docs = docs
        self.distancias = distancias or [0.5 * (i + 1) for i in range(len(docs))]
        self.ultima = None
        self._collection = types.SimpleNamespace(metadata={"hnsw:space": espaco} if espaco else None)

    def similarity_search_with_score(self, query, k):
        self.ultima = (query, k)
        return list(zip(self.docs, self.distancias))


class RotuloFonteTest(unittest.TestCase):
    def test_rotulos(self):
        casos = {
            "/home/x/p/data/rulebooks/core/Player's Handbook (2024).md": "Core | Player's Handbook (2024)",
            "/home/x/p/data/rulebooks/suplements/Xanathar's Guide to Everything.md": "Suplemento | Xanathar's Guide to Everything",
            "C:\\proj\\data\\rulebooks\\core\\Monster Manual (2025).md": "Core | Monster Manual (2025)",
            "/tmp/qualquer.md": "Livro | qualquer",
        }
        for caminho, esperado in casos.items():
            with self.subTest(caminho=caminho):
                self.assertEqual(rag.rotulo_fonte(caminho), esperado)


class SimilaridadeTest(unittest.TestCase):
    def test_espaco_l2_com_vetores_normalizados(self):
        self.assertAlmostEqual(rag.distancia_para_similaridade(0.0), 1.0)
        self.assertAlmostEqual(rag.distancia_para_similaridade(1.0), 0.5)
        self.assertAlmostEqual(rag.distancia_para_similaridade(math.sqrt(2)), 0.0)  # vetores ortogonais
        self.assertAlmostEqual(rag.distancia_para_similaridade(2.0), -1.0)          # vetores opostos

    def test_espaco_cosseno(self):
        self.assertAlmostEqual(rag.distancia_para_similaridade(0.25, "cosine"), 0.75)


class BuscarContextoTest(BaseTeste):
    def test_sem_base_levanta_erro_com_instrucao(self):
        with mock.patch.object(rag, "_vector_store", None):
            with self.assertRaisesRegex(BaseVaziaError, "rpgassistant.indexar"):
                rag.buscar_contexto("agarrar")

    def test_melhor_similaridade_e_trechos(self):
        banco = BancoFalso([Doc("A", {"source": "/x/rulebooks/core/PHB.md"}), Doc("B", {"source": "/x/rulebooks/core/DMG.md"})],
                           distancias=[0.6, 1.2])
        with mock.patch.object(rag, "_vector_store", banco):
            resultado = rag.buscar_contexto("agarrar", k=2)
        self.assertAlmostEqual(resultado.melhor_similaridade, 1 - 0.36 / 2)
        self.assertEqual(resultado.trechos, 2)
        self.assertEqual(resultado.fontes, "Core | PHB, Core | DMG")

    def test_usa_o_espaco_de_cosseno_da_base(self):
        banco = BancoFalso([Doc("A", {"source": "/x/rulebooks/core/PHB.md"})], distancias=[0.2], espaco="cosine")
        with mock.patch.object(rag, "_vector_store", banco):
            self.assertAlmostEqual(rag.buscar_contexto("x").melhor_similaridade, 0.8)

    def test_busca_sem_resultados(self):
        with mock.patch.object(rag, "_vector_store", BancoFalso([])):
            resultado = rag.buscar_contexto("x")
        self.assertEqual((resultado.melhor_similaridade, resultado.trechos, resultado.fontes), (None, 0, "Desconhecido"))


class RecuperarContextoTest(BaseTeste):
    def test_sem_base_nao_carrega_embeddings(self):
        with mock.patch.object(rag, "_vector_store", None), \
             mock.patch.object(rag, "get_embeddings", side_effect=AssertionError("não deveria carregar")):
            self.assertIsNone(rag.load_vector_store())
            contexto, fontes = rag.recuperar_contexto("agarrar")
        self.assertIn("Base vetorial não inicializada", contexto)
        self.assertEqual(fontes, "Nenhuma fonte")

    def test_rotulos_ordem_e_pagina_zero(self):
        banco = BancoFalso([
            Doc("A", {"source": "/x/rulebooks/core/PHB.md"}),
            Doc("B", {"source": "/x/rulebooks/suplements/Tasha.md"}),
            Doc("C", {"source": "/x/rulebooks/core/PHB.md"}),
            Doc("D", {"source": "/x/rulebooks/core/Livro.pdf", "page": 0}),
        ])
        with mock.patch.object(rag, "_vector_store", banco):
            contexto, fontes = rag.recuperar_contexto("agarrar", k=4)
        self.assertEqual(fontes, "Core | PHB, Suplemento | Tasha, Core | Livro - pág. 1")
        self.assertIn("[Fonte: Suplemento | Tasha]", contexto)
        self.assertEqual(banco.ultima, ("agarrar", 4))

    def test_k_padrao_vem_da_configuracao(self):
        banco = BancoFalso([Doc("A", {"source": "/x/rulebooks/core/PHB.md"})])
        with mock.patch.object(rag, "_vector_store", banco):
            rag.recuperar_contexto("agarrar")
        self.assertEqual(banco.ultima[1], 8)

    def test_busca_sem_resultados(self):
        with mock.patch.object(rag, "_vector_store", BancoFalso([])):
            self.assertEqual(rag.recuperar_contexto("x"), ("Nenhum trecho relevante encontrado.", "Desconhecido"))


class ReescreverPerguntaTest(BaseTeste):
    HISTORICO = [{"role": "user", "content": "Como funciona Amedrontado?"}, {"role": "assistant", "content": "Resposta..."}]

    def test_sem_historico_nao_chama_o_modelo(self):
        falso = self.usar_ollama(OllamaFalso())
        self.assertEqual(rag.reescrever_pergunta("oi", []), "oi")
        self.assertEqual(falso.chamadas, [])

    def test_reescreve_usando_so_a_primeira_linha(self):
        falso = self.usar_ollama(OllamaFalso(
            responder=lambda kw: resposta('"Como a condição Amedrontado funciona para um personagem cego?"\nexplicação extra')))
        nova = rag.reescrever_pergunta("e se eu estiver cego?", self.HISTORICO)
        self.assertEqual(nova, "Como a condição Amedrontado funciona para um personagem cego?")
        self.assertEqual(falso.chamadas[0]["options"]["temperature"], 0)

    def test_resposta_curta_demais_usa_a_original(self):
        self.usar_ollama(OllamaFalso("x"))
        self.assertEqual(rag.reescrever_pergunta("e se?", self.HISTORICO), "e se?")

    def test_falha_do_ollama_usa_a_original(self):
        self.usar_ollama(OllamaFalso(falha=ConnectionError("fora do ar")))
        self.assertEqual(rag.reescrever_pergunta("e se?", self.HISTORICO), "e se?")


if __name__ == "__main__":
    unittest.main()