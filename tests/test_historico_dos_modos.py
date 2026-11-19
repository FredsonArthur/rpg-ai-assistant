"""
Histórico enviado ao modelo em cada modo
----------------------------------------
O Assistente e os outros modos escolhem as mensagens recentes de jeitos diferentes, de propósito:

- Mestre e Jogador usam `janela_historico`: a conversa abre com uma fala do assistente (a abertura da
  cena ou a saudação) e essa abertura é sempre preservada.
- O Assistente usa uma fatia simples: a conversa abre com a pergunta do usuário, e `janela_historico`
  deixaria duas falas do usuário seguidas.

Estes testes travam essa decisão, para que ninguém "unifique" os dois sem perceber o problema.
"""

import unittest

from rpgassistant.core.historico import janela_historico
from rpgassistant.modes import assistente
from tests.helpers import BaseTeste, OllamaFalso, modelo


def conversa(n, abre_com):
    """Conversa de `n` mensagens que alterna os papéis, começando por `abre_com`."""
    outro = "assistant" if abre_com == "user" else "user"
    return [{"role": abre_com if i % 2 == 0 else outro, "content": f"m{i}"} for i in range(n)]


def papeis(mensagens):
    return [m["role"] for m in mensagens]


def sem_falas_seguidas_do_mesmo_papel(mensagens):
    return all(a["role"] != b["role"] for a, b in zip(mensagens, mensagens[1:]))


class JanelaHistoricoTest(unittest.TestCase):
    def test_conversa_que_abre_com_o_assistente_preserva_a_abertura_e_alterna(self):
        historico = conversa(30, abre_com="assistant")
        janela = janela_historico(historico, 10)
        self.assertEqual(janela[0]["content"], "m0")  # a abertura da cena continua lá
        self.assertTrue(sem_falas_seguidas_do_mesmo_papel(janela))

    def test_conversa_que_abre_com_o_usuario_fica_com_duas_falas_seguidas(self):
        """Isto NÃO é desejável: é o motivo de o Assistente não usar `janela_historico`."""
        janela = janela_historico(conversa(30, abre_com="user"), 10)
        self.assertEqual(papeis(janela[:2]), ["user", "user"])


class HistoricoDoAssistenteTest(BaseTeste):
    def preparar(self, historico):
        self.usar_ollama(OllamaFalso(responder=modelo))
        self.usar_busca(similaridade=0.8)
        return assistente.preparar("e se eu estiver cego?", historico)

    def test_conversa_longa_envia_as_ultimas_dez_alternando_e_comecando_pelo_usuario(self):
        historico = conversa(30, abre_com="user")
        consulta = self.preparar(historico)
        enviadas = consulta.mensagens[1:-1]  # sem o prompt do sistema e sem a pergunta atual
        self.assertEqual(enviadas, historico[-10:])
        self.assertEqual(papeis(enviadas)[0], "user")
        self.assertTrue(sem_falas_seguidas_do_mesmo_papel(consulta.mensagens[1:]))  # inclui a pergunta atual
        self.assertEqual(len(consulta.mensagens), 12)

    def test_conversa_curta_vai_inteira(self):
        historico = conversa(4, abre_com="user")
        consulta = self.preparar(historico)
        self.assertEqual(consulta.mensagens[1:-1], historico)

    def test_a_primeira_pergunta_antiga_nao_e_reenviada(self):
        consulta = self.preparar(conversa(30, abre_com="user"))
        conteudos = [m["content"] for m in consulta.mensagens]
        self.assertNotIn("m0", conteudos)


if __name__ == "__main__":
    unittest.main()