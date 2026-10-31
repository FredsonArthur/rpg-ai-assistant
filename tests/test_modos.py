import unittest

from rpgassistant.core import modos
from rpgassistant.core.modos import MODO_ASSISTENTE as AS, MODO_JOGADOR as JO, MODO_MESTRE as ME


class InterpretarEntradaTest(unittest.TestCase):
    def conferir(self, texto, modo, tipo, alvo=None):
        acao = modos.interpretar_entrada(texto, modo)
        self.assertEqual((acao.tipo, acao.modo), (tipo, alvo), f"[{modo}] {texto!r}")

    def test_comandos_valem_em_qualquer_modo(self):
        for texto, alvo in (("/mestre", ME), ("/Jogador", JO), ("/assistente", AS), ("  /MESTRE  ", ME)):
            with self.subTest(texto=texto):
                self.conferir(texto, AS, "trocar_modo", alvo)
        self.conferir("/assistente", ME, "trocar_modo", AS)
        self.conferir("/mestre", JO, "trocar_modo", ME)
        self.conferir("/ajuda", AS, "ajuda")
        self.conferir("/xyz", AS, "ajuda")
        self.conferir("/feedback", JO, "feedback")

    def test_pedidos_para_a_ia_virar_mestre(self):
        for texto in ("seja meu mestre", "Quero que você seja o mestre de uma aventura", "atue como mestre",
                      "Pode ser meu mestre?", "vamos jogar uma aventura solo", "Quero jogar uma aventura",
                      "quero ser o jogador", "faça o papel de mestre", "Inicie uma aventura numa masmorra",
                      "você será o mestre"):
            with self.subTest(texto=texto):
                self.conferir(texto, AS, "trocar_modo", ME)

    def test_pedidos_para_a_ia_virar_jogador(self):
        for texto in ("seja meu jogador", "atue como um jogador iniciante", "quero ser o mestre", "eu vou mestrar",
                      "Quero treinar como mestre", "Quero que você seja um jogador tático", "quero mestrar",
                      "pode ser meu jogador?"):
            with self.subTest(texto=texto):
                self.conferir(texto, AS, "trocar_modo", JO)

    def test_perguntas_e_mensagens_comuns_nao_trocam_de_modo(self):
        for texto in ("Como funciona a ação de Agarrar?", "Qual o papel do mestre em um combate?",
                      "Como ser um bom mestre?", "O mestre pode negar um teste?", "O jogador pode usar duas reações?",
                      "crie um NPC mestre de guilda", "Quero jogar D&D, quais são as regras básicas?",
                      "Quero ser mestre, por onde começar?", "Quero jogar uma partida de D&D, como funciona a iniciativa?",
                      "O que é uma rede neural?", "oi", "Explique o que um jogador iniciante deve saber"):
            with self.subTest(texto=texto):
                self.conferir(texto, AS, "mensagem")

    def test_texto_longo_nao_e_pedido(self):
        self.conferir("seja meu mestre " + "e " * 150, AS, "mensagem")

    def test_dentro_de_uma_sessao_so_comandos_trocam_de_modo(self):
        self.conferir("seja meu mestre", JO, "mensagem")
        self.conferir("quero ser o mestre", ME, "mensagem")
        self.conferir("O mestre da guilda manda você atuar com cuidado", ME, "mensagem")
        self.conferir("Saio da taverna e volto para a estalagem", ME, "mensagem")

    def test_voltar_ao_assistente(self):
        self.conferir("voltar ao assistente", JO, "trocar_modo", AS)
        self.conferir("Volte ao modo assistente, por favor", ME, "trocar_modo", AS)
        self.conferir("modo assistente", ME, "trocar_modo", AS)
        self.conferir("voltar ao assistente", AS, "mensagem")


class HistoricoParaLlmTest(unittest.TestCase):
    def setUp(self):
        self.mensagens = [
            {"role": "user", "content": "regra?", "mode": AS, "sessao": 0},
            {"role": "assistant", "content": "resp", "mode": AS, "sessao": 0},
            {"role": "sistema", "content": "aviso", "mode": None, "sessao": 0},
            {"role": "assistant", "content": "abertura1", "mode": ME, "sessao": 1, "estado": "x"},
            {"role": "user", "content": "ação1", "mode": ME, "sessao": 1},
            {"role": "assistant", "content": "abertura2", "mode": ME, "sessao": 2},
            {"role": "sistema", "content": "feedback", "mode": None, "sessao": 0, "kind": "feedback"},
        ]

    def conteudos(self, modo, sessao):
        return [m["content"] for m in modos.historico_para_llm(self.mensagens, modo, sessao)]

    def test_so_as_falas_do_modo_e_da_sessao(self):
        self.assertEqual(self.conteudos(AS, 0), ["regra?", "resp"])
        self.assertEqual(self.conteudos(ME, 1), ["abertura1", "ação1"])
        self.assertEqual(self.conteudos(ME, 2), ["abertura2"])
        self.assertEqual(self.conteudos(JO, 0), [])

    def test_so_role_e_content_seguem_ao_modelo(self):
        for msg in modos.historico_para_llm(self.mensagens, ME, 1):
            self.assertEqual(set(msg), {"role", "content"})


if __name__ == "__main__":
    unittest.main()