import unittest

from rpgassistant.core import mode_selection
from rpgassistant.core.modos import MODO_ASSISTENTE as AS, MODO_JOGADOR as JO, MODO_MESTRE as ME


class EscolherModoTest(unittest.TestCase):
    def conferir(self, texto, modo, pergunta=False, ajuda=False):
        escolha = mode_selection.escolher_modo(texto)
        self.assertEqual((escolha.modo, escolha.pergunta, escolha.ajuda), (modo, pergunta, ajuda), repr(texto))

    def test_numero_ou_nome_da_opcao(self):
        for texto, modo in (("1", AS), ("2", ME), ("3", JO), ("1)", AS), ("2.", ME), ("assistente", AS), ("Mestre", ME),
                            ("JOGADOR", JO), ("quero o jogador", JO), ("modo assistente", AS), ("opção 2", ME),
                            ("escolho o mestre", ME), ("  3  ", JO)):
            with self.subTest(texto=texto):
                self.conferir(texto, modo)

    def test_comandos(self):
        self.conferir("/mestre", ME)
        self.conferir("/Jogador", JO)
        self.conferir("/assistente", AS)
        self.conferir("/ajuda", None, ajuda=True)
        self.conferir("/xyz", None, ajuda=True)

    def test_pedidos_em_linguagem_natural(self):
        for texto, modo in (("seja meu mestre", ME), ("Quero que você seja o mestre de uma aventura", ME),
                            ("vamos jogar uma aventura solo", ME), ("seja meu jogador", JO), ("quero ser o mestre", JO),
                            ("eu vou mestrar", JO), ("atue como um jogador iniciante", JO)):
            with self.subTest(texto=texto):
                self.conferir(texto, modo)

    def test_pergunta_de_regras_vira_assistente_automaticamente(self):
        for texto in ("Como funciona a condição Agarrado?", "como funciona agarrar", "O que é vantagem?",
                      "Qual o dano de uma queda", "explique a iniciativa", "Crie um NPC estalajadeiro",
                      "Quero ser mestre, por onde começar?", "agarrar?", "Posso usar duas reações por turno",
                      "Quais raças existem?"):
            with self.subTest(texto=texto):
                self.conferir(texto, AS, pergunta=True)

    def test_mensagens_sem_pedido_nem_pergunta_repetem_as_opcoes(self):
        for texto in ("oi", "olá", "bom dia", "teste", "quero jogar", "agarrar", "ok", "sim"):
            with self.subTest(texto=texto):
                self.conferir(texto, None)

    def test_parece_pergunta(self):
        self.assertTrue(mode_selection.parece_pergunta("como faço isso"))
        self.assertTrue(mode_selection.parece_pergunta("Como?"))
        self.assertFalse(mode_selection.parece_pergunta("comovente"))  # "como" só vale como palavra inteira
        self.assertFalse(mode_selection.parece_pergunta("?"))

    def test_mensagens_de_orientacao_citam_as_tres_opcoes(self):
        for texto in (mode_selection.MSG_BOAS_VINDAS, mode_selection.MSG_REPETIR):
            for palavra in ("Assistente", "Mestre", "Jogador"):
                self.assertIn(palavra, texto)


if __name__ == "__main__":
    unittest.main()