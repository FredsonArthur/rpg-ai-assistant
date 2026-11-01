import unittest

from rpgassistant.core import modos
from rpgassistant.core.modos import MODO_ASSISTENTE, MODO_JOGADOR as JO, MODO_MESTRE as ME


class DetectarPedidoDeModoTest(unittest.TestCase):
    def conferir(self, texto, esperado):
        self.assertEqual(modos.detectar_pedido_de_modo(texto), esperado, repr(texto))

    def test_pedidos_para_a_ia_virar_mestre(self):
        for texto in ("seja meu mestre", "Quero que você seja o mestre de uma aventura", "atue como mestre",
                      "Pode ser meu mestre?", "vamos jogar uma aventura solo", "Quero jogar uma aventura",
                      "quero ser o jogador", "faça o papel de mestre", "Inicie uma aventura numa masmorra",
                      "você será o mestre"):
            with self.subTest(texto=texto):
                self.conferir(texto, ME)

    def test_pedidos_para_a_ia_virar_jogador(self):
        for texto in ("seja meu jogador", "atue como um jogador iniciante", "quero ser o mestre", "eu vou mestrar",
                      "Quero treinar como mestre", "Quero que você seja um jogador tático", "quero mestrar",
                      "pode ser meu jogador?"):
            with self.subTest(texto=texto):
                self.conferir(texto, JO)

    def test_perguntas_e_mensagens_comuns_nao_sao_pedidos(self):
        for texto in ("Como funciona a ação de Agarrar?", "Qual o papel do mestre em um combate?",
                      "Como ser um bom mestre?", "O mestre pode negar um teste?", "O jogador pode usar duas reações?",
                      "crie um NPC mestre de guilda", "Quero jogar D&D, quais são as regras básicas?",
                      "Quero ser mestre, por onde começar?", "Quero jogar uma partida de D&D, como funciona a iniciativa?",
                      "O que é uma rede neural?", "oi", "Explique o que um jogador iniciante deve saber"):
            with self.subTest(texto=texto):
                self.conferir(texto, None)

    def test_texto_longo_nao_e_pedido(self):
        self.conferir("seja meu mestre " + "e " * 150, None)

    def test_pedidos_contraditorios_nao_escolhem_modo(self):
        self.conferir("quero que você seja meu mestre e eu vou mestrar", None)


class NormalizarTest(unittest.TestCase):
    def test_sem_acentos_e_em_minusculas(self):
        self.assertEqual(modos.normalizar("Você É o MESTRE? Ação!"), "voce e o mestre? acao!")


class ConstantesTest(unittest.TestCase):
    def test_modos_e_rotulos(self):
        self.assertEqual(modos.MODOS, [MODO_ASSISTENTE, ME, JO])
        self.assertEqual(set(modos.ROTULOS_MODO), set(modos.MODOS))


if __name__ == "__main__":
    unittest.main()