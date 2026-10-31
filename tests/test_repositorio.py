import unittest
from unittest import mock

from rpgassistant.core.models import TITULO_PADRAO
from rpgassistant.errors import ChatNaoEncontrado
from rpgassistant.storage.database import Database
from rpgassistant.storage.repository import RepositorioChats
from tests.helpers import RelogioFalso


class RepositorioTest(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.addCleanup(self.db.fechar)
        self.repo = RepositorioChats(self.db, agora=RelogioFalso())

    # ---------- chats ----------
    def test_criar_e_obter(self):
        chat = self.repo.criar_chat()
        self.assertEqual((chat.titulo, chat.modo, chat.estado), (TITULO_PADRAO, None, {}))
        self.assertEqual(self.repo.obter_chat(chat.id), chat)

    def test_criar_com_titulo_modo_e_estado(self):
        chat = self.repo.criar_chat("  Aventura   na tumba ", "mestre", {"cenario": "Tumba"})
        self.assertEqual((chat.titulo, chat.modo, chat.estado), ("Aventura na tumba", "mestre", {"cenario": "Tumba"}))

    def test_modo_invalido(self):
        with self.assertRaises(ValueError):
            self.repo.criar_chat(modo="narrador")
        chat = self.repo.criar_chat()
        with self.assertRaises(ValueError):
            self.repo.definir_modo(chat.id, "narrador")

    def test_listar_do_mais_recente_para_o_mais_antigo(self):
        a, b, c = (self.repo.criar_chat(t) for t in ("A", "B", "C"))
        self.assertEqual([x.titulo for x in self.repo.listar_chats()], ["C", "B", "A"])
        self.repo.adicionar_mensagem(a.id, "user", "oi")  # atividade em A: ele sobe para o topo
        self.assertEqual([x.titulo for x in self.repo.listar_chats()], ["A", "C", "B"])

    def test_renomear(self):
        chat = self.repo.criar_chat()
        self.assertEqual(self.repo.renomear_chat(chat.id, "  Novo   nome ").titulo, "Novo nome")
        with self.assertRaises(ValueError):
            self.repo.renomear_chat(chat.id, "   ")
        self.assertEqual(self.repo.obter_chat(chat.id).titulo, "Novo nome")

    def test_estado_vai_e_volta_com_acentos_e_aninhamento(self):
        chat = self.repo.criar_chat()
        estado = {"cenario": "Floresta Sombria e Pântano dos Goblins", "personagem": {"nome": "Lia", "pv": [8, 8]},
                  "estado_combate": "Jogador PV 11/15 | Goblin PV 7/7 CA 15"}
        self.repo.salvar_estado(chat.id, estado)
        self.assertEqual(self.repo.obter_chat(chat.id).estado, estado)

    def test_excluir_apaga_as_mensagens_em_cascata(self):
        chat = self.repo.criar_chat()
        self.repo.adicionar_mensagem(chat.id, "user", "oi")
        outro = self.repo.criar_chat("B")
        self.repo.adicionar_mensagem(outro.id, "user", "tchau")
        self.repo.excluir_chat(chat.id)
        self.assertEqual(self.db.valor("SELECT COUNT(*) FROM mensagens"), 1)
        self.assertEqual([c.id for c in self.repo.listar_chats()], [outro.id])

    def test_chat_inexistente(self):
        operacoes = [
            lambda: self.repo.obter_chat(99),
            lambda: self.repo.renomear_chat(99, "x"),
            lambda: self.repo.definir_modo(99, "mestre"),
            lambda: self.repo.salvar_estado(99, {}),
            lambda: self.repo.excluir_chat(99),
            lambda: self.repo.adicionar_mensagem(99, "user", "x"),
            lambda: self.repo.listar_mensagens(99),
        ]
        for operacao in operacoes:
            with self.subTest(operacao=operacao):
                with self.assertRaises(ChatNaoEncontrado):
                    operacao()

    # ---------- mensagens ----------
    def test_ordem_sequencial_por_chat(self):
        a, b = self.repo.criar_chat("A"), self.repo.criar_chat("B")
        for texto in ("1", "2", "3"):
            self.repo.adicionar_mensagem(a.id, "user", texto)
        self.repo.adicionar_mensagem(b.id, "user", "x")
        self.assertEqual([(m.ordem, m.conteudo) for m in self.repo.listar_mensagens(a.id)], [(1, "1"), (2, "2"), (3, "3")])
        self.assertEqual([m.ordem for m in self.repo.listar_mensagens(b.id)], [1])

    def test_a_ordem_continua_depois_de_reabrir_o_repositorio(self):
        chat = self.repo.criar_chat()
        self.repo.adicionar_mensagem(chat.id, "user", "1")
        outro = RepositorioChats(self.db, agora=RelogioFalso())
        self.assertEqual(outro.adicionar_mensagem(chat.id, "assistant", "2").ordem, 2)

    def test_extras_tipo_e_papel(self):
        chat = self.repo.criar_chat()
        extras = {"fontes": "Core | PHB", "metricas": "Prompt Tokens: 7", "estado": "Jogador PV 3/10"}
        salva = self.repo.adicionar_mensagem(chat.id, "assistant", "Resposta com acentuação: ção", "fala", extras)
        lida = self.repo.listar_mensagens(chat.id)[0]
        self.assertEqual(lida, salva)
        self.assertEqual((lida.papel, lida.tipo, lida.extras, lida.conteudo),
                         ("assistant", "fala", extras, "Resposta com acentuação: ção"))

    def test_papel_e_tipo_invalidos(self):
        chat = self.repo.criar_chat()
        with self.assertRaises(ValueError):
            self.repo.adicionar_mensagem(chat.id, "robo", "x")
        with self.assertRaises(ValueError):
            self.repo.adicionar_mensagem(chat.id, "user", "x", tipo="inventado")
        self.assertEqual(self.repo.contar_mensagens(chat.id), 0)

    def test_mensagem_com_aviso_do_sistema(self):
        chat = self.repo.criar_chat()
        msg = self.repo.adicionar_mensagem(chat.id, "sistema", "Feedback...", "feedback")
        self.assertEqual((msg.papel, msg.tipo), ("sistema", "feedback"))

    def test_falha_no_meio_nao_deixa_mensagem_pela_metade(self):
        chat = self.repo.criar_chat()
        original = self.db.executar

        def falha_no_update(sql, parametros=()):
            if sql.startswith("UPDATE chats SET atualizado_em"):
                raise RuntimeError("falha simulada")
            return original(sql, parametros)

        with mock.patch.object(self.db, "executar", falha_no_update):
            with self.assertRaises(RuntimeError):
                self.repo.adicionar_mensagem(chat.id, "user", "oi")
        self.assertEqual(self.repo.contar_mensagens(chat.id), 0)
        self.assertEqual(self.repo.adicionar_mensagem(chat.id, "user", "oi").ordem, 1)

    def test_excluir_mensagem(self):
        chat, outro = self.repo.criar_chat("A"), self.repo.criar_chat("B")
        self.repo.adicionar_mensagem(chat.id, "user", "1")
        segunda = self.repo.adicionar_mensagem(chat.id, "assistant", "2")
        self.repo.excluir_mensagem(chat.id, segunda.id)
        self.assertEqual([m.conteudo for m in self.repo.listar_mensagens(chat.id)], ["1"])
        self.assertEqual(self.repo.adicionar_mensagem(chat.id, "assistant", "3").ordem, 2)  # a numeração segue em frente
        with self.assertRaises(ChatNaoEncontrado):
            self.repo.excluir_mensagem(chat.id, segunda.id)          # já foi apagada
        with self.assertRaises(ChatNaoEncontrado):
            self.repo.excluir_mensagem(outro.id, 1)                  # a mensagem é de outro chat
        self.assertEqual(self.repo.contar_mensagens(chat.id), 2)

    def test_json_ilegivel_nao_derruba_o_app(self):
        chat = self.repo.criar_chat()
        self.db.executar("UPDATE chats SET estado = 'isso não é json' WHERE id = ?", (chat.id,))
        self.assertEqual(self.repo.obter_chat(chat.id).estado, {})

    def test_datas_e_atividade(self):
        chat = self.repo.criar_chat()
        antes = self.repo.obter_chat(chat.id).atualizado_em
        self.repo.adicionar_mensagem(chat.id, "user", "oi")
        depois = self.repo.obter_chat(chat.id).atualizado_em
        self.assertGreater(depois, antes)
        self.assertEqual(self.repo.obter_chat(chat.id).criado_em, chat.criado_em)


if __name__ == "__main__":
    unittest.main()