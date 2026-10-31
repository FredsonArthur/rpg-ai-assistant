import unittest
from pathlib import Path

from rpgassistant.core.chats import GerenciadorDeChats, para_historico
from rpgassistant.core.models import TITULO_PADRAO
from rpgassistant.errors import ChatNaoEncontrado, ModoJaDefinidoError
from rpgassistant.storage.database import Database
from rpgassistant.storage.repository import RepositorioChats
from tests.helpers import BaseTeste, RelogioFalso


def gerenciador_em_memoria() -> GerenciadorDeChats:
    return GerenciadorDeChats(RepositorioChats(Database(":memory:"), agora=RelogioFalso()))


class GerenciadorTest(unittest.TestCase):
    def setUp(self):
        self.g = gerenciador_em_memoria()
        self.addCleanup(self.g.fechar)

    def test_novo_chat_vira_o_atual(self):
        chat = self.g.novo_chat()
        self.assertEqual(self.g.chat_atual, chat)
        self.assertEqual((chat.titulo, chat.modo), (TITULO_PADRAO, None))

    def test_novo_chat_reaproveita_o_chat_em_branco(self):
        primeiro = self.g.novo_chat()
        self.assertEqual(self.g.novo_chat().id, primeiro.id)
        self.assertEqual(len(self.g.listar()), 1)

    def test_as_boas_vindas_nao_impedem_o_reaproveitamento(self):
        primeiro = self.g.novo_chat()
        self.g.registrar(primeiro.id, "assistant", "Como você quer usar o assistente?", "aviso")
        self.assertEqual(self.g.novo_chat().id, primeiro.id)
        self.assertEqual(len(self.g.listar()), 1)

    def test_chat_com_mensagem_do_usuario_nao_e_reaproveitado(self):
        primeiro = self.g.novo_chat()
        self.g.registrar(primeiro.id, "user", "oi", "aviso")  # o modo ainda não foi escolhido, mas o usuário já escreveu
        self.assertNotEqual(self.g.novo_chat().id, primeiro.id)

    def test_novo_chat_nao_reaproveita_chat_usado(self):
        com_modo = self.g.novo_chat()
        self.g.definir_modo(com_modo.id, "assistente")
        com_mensagem = self.g.novo_chat()
        self.assertNotEqual(com_mensagem.id, com_modo.id)
        self.g.registrar(com_mensagem.id, "user", "oi")
        outro = self.g.novo_chat()
        self.assertNotIn(outro.id, (com_modo.id, com_mensagem.id))
        self.assertEqual(len(self.g.listar()), 3)

    def test_abrir_chat(self):
        a = self.g.novo_chat()
        self.g.definir_modo(a.id, "mestre")
        b = self.g.novo_chat()
        self.assertEqual(self.g.chat_atual.id, b.id)
        self.assertEqual(self.g.abrir_chat(a.id).id, a.id)
        self.assertEqual(self.g.chat_atual.id, a.id)
        with self.assertRaises(ChatNaoEncontrado):
            self.g.abrir_chat(999)

    def test_restaurar_ultimo(self):
        self.assertIsNone(self.g.restaurar_ultimo())
        a = self.g.novo_chat()
        self.g.definir_modo(a.id, "mestre")
        b = self.g.novo_chat()
        self.g.registrar(a.id, "user", "oi")  # a teve a atividade mais recente
        self.assertEqual(self.g.restaurar_ultimo().id, a.id)
        self.assertEqual(self.g.chat_atual.id, a.id)
        self.assertNotEqual(a.id, b.id)

    def test_renomear(self):
        chat = self.g.novo_chat()
        self.assertEqual(self.g.renomear(chat.id, "Minha campanha").titulo, "Minha campanha")
        with self.assertRaises(ValueError):
            self.g.renomear(chat.id, "")

    def test_excluir_o_chat_atual_abre_o_mais_recente(self):
        a = self.g.novo_chat()
        self.g.definir_modo(a.id, "assistente")
        b = self.g.novo_chat()
        self.g.definir_modo(b.id, "mestre")
        c = self.g.novo_chat()
        self.assertEqual(self.g.excluir(c.id).id, b.id)
        self.assertEqual(self.g.chat_atual.id, b.id)

    def test_excluir_outro_chat_mantem_o_atual(self):
        a = self.g.novo_chat()
        self.g.definir_modo(a.id, "assistente")
        b = self.g.novo_chat()
        self.assertEqual(self.g.excluir(a.id).id, b.id)
        self.assertEqual([c.id for c in self.g.listar()], [b.id])

    def test_excluir_o_ultimo_chat(self):
        chat = self.g.novo_chat()
        self.assertIsNone(self.g.excluir(chat.id))
        self.assertIsNone(self.g.chat_atual)
        self.assertEqual(self.g.listar(), [])

    def test_excluir_chat_inexistente(self):
        with self.assertRaises(ChatNaoEncontrado):
            self.g.excluir(42)

    def test_chat_atual_excluido_por_fora_vira_none(self):
        chat = self.g.novo_chat()
        self.g.repositorio.excluir_chat(chat.id)
        self.assertIsNone(self.g.chat_atual)

    def test_modo_so_pode_ser_escolhido_uma_vez(self):
        chat = self.g.novo_chat()
        self.assertEqual(self.g.definir_modo(chat.id, "mestre").modo, "mestre")
        self.assertEqual(self.g.definir_modo(chat.id, "mestre").modo, "mestre")  # repetir é inofensivo
        with self.assertRaises(ModoJaDefinidoError):
            self.g.definir_modo(chat.id, "jogador")
        self.assertEqual(self.g.chat_atual.modo, "mestre")

    def test_modo_invalido(self):
        with self.assertRaises(ValueError):
            self.g.definir_modo(self.g.novo_chat().id, "narrador")

    def test_titulo_automatico_so_troca_o_titulo_padrao(self):
        chat = self.g.novo_chat()
        self.assertEqual(self.g.titulo_automatico(chat.id, "Como funciona agarrar?").titulo, "Como funciona agarrar?")
        self.assertEqual(self.g.titulo_automatico(chat.id, "Outra pergunta").titulo, "Como funciona agarrar?")
        manual = self.g.novo_chat()
        self.g.registrar(manual.id, "user", "x")
        self.g.renomear(manual.id, "Meu nome")
        self.assertEqual(self.g.titulo_automatico(manual.id, "texto qualquer").titulo, "Meu nome")

    def test_estado_e_mesclado(self):
        chat = self.g.novo_chat()
        self.assertEqual(self.g.atualizar_estado(chat.id, cenario="Tumba", personagem="Guerreiro"),
                         {"cenario": "Tumba", "personagem": "Guerreiro"})
        self.assertEqual(self.g.atualizar_estado(chat.id, estado_combate="Jogador PV 9/15"),
                         {"cenario": "Tumba", "personagem": "Guerreiro", "estado_combate": "Jogador PV 9/15"})
        self.assertEqual(self.g.estado(chat.id)["cenario"], "Tumba")

    def test_historico_so_leva_as_falas_ao_modelo(self):
        chat = self.g.novo_chat()
        self.g.registrar(chat.id, "assistant", "abertura")
        self.g.registrar(chat.id, "sistema", "Modo alterado", "aviso")
        self.g.registrar(chat.id, "user", "ataco", extras={"x": 1})
        self.g.registrar(chat.id, "sistema", "Pontos Fortes...", "feedback")
        self.g.registrar(chat.id, "sistema", "ajuda", "ajuda")
        self.g.registrar(chat.id, "assistant", "o goblin cai", extras={"estado": "Sem combate"})
        self.assertEqual(self.g.historico_para_llm(chat.id), [
            {"role": "assistant", "content": "abertura"},
            {"role": "user", "content": "ataco"},
            {"role": "assistant", "content": "o goblin cai"},
        ])
        self.assertEqual(len(self.g.mensagens(chat.id)), 6)  # tudo fica salvo e exibível

    def test_descartar_desfaz_uma_mensagem(self):
        chat = self.g.novo_chat()
        pergunta = self.g.registrar(chat.id, "user", "pergunta sem resposta")
        self.g.descartar(pergunta)
        self.assertEqual(self.g.mensagens(chat.id), [])
        self.assertEqual(self.g.registrar(chat.id, "user", "de novo").ordem, 1)

    def test_chats_sao_independentes(self):
        a, b = self.g.novo_chat(), None
        self.g.definir_modo(a.id, "assistente")
        b = self.g.novo_chat()
        self.g.definir_modo(b.id, "mestre")
        self.g.registrar(a.id, "user", "pergunta de regras")
        self.g.registrar(b.id, "user", "ataco o goblin")
        self.g.atualizar_estado(b.id, estado_combate="Goblin PV 3/7")
        self.assertEqual([m.conteudo for m in self.g.mensagens(a.id)], ["pergunta de regras"])
        self.assertEqual([m.conteudo for m in self.g.mensagens(b.id)], ["ataco o goblin"])
        self.assertEqual(self.g.estado(a.id), {})
        self.assertEqual(para_historico(self.g.mensagens(a.id)), [{"role": "user", "content": "pergunta de regras"}])


class ReiniciarOAppTest(BaseTeste):
    """Fechar e abrir o app de novo precisa devolver tudo como estava."""

    def test_tudo_volta_depois_de_reiniciar(self):
        g = GerenciadorDeChats.abrir()  # usa o banco padrão da configuração
        self.assertEqual(Path(g.repositorio.db.caminho), self.cfg.chats_db)

        regras = g.novo_chat()
        g.definir_modo(regras.id, "assistente")
        g.titulo_automatico(regras.id, "Como funciona a condição Agarrado?")
        g.registrar(regras.id, "user", "Como funciona a condição Agarrado?")
        g.registrar(regras.id, "assistant", "Agarrado [Grappled] reduz a velocidade a 0.",
                    extras={"fontes": "Core | Player's Handbook (2024)", "metricas": "Prompt Tokens: 812"})

        aventura = g.novo_chat()
        g.definir_modo(aventura.id, "mestre")
        g.renomear(aventura.id, "Tumba antiga")
        g.atualizar_estado(aventura.id, cenario="Masmorra nas Ruínas de uma Tumba Antiga",
                           personagem="Guerreiro Humano, Nível 2", estado_combate="Jogador PV 11/15 | Goblin PV 7/7 CA 15")
        g.registrar(aventura.id, "assistant", "Você vê um corredor escuro. O que você faz?")
        g.registrar(aventura.id, "user", "Ataco o goblin")
        g.registrar(aventura.id, "sistema", "Aventura iniciada", "aviso")
        g.fechar()

        # --- o app é fechado e aberto de novo ---
        g2 = GerenciadorDeChats.abrir()
        self.assertEqual([c.titulo for c in g2.listar()], ["Tumba antiga", "Como funciona a condição Agarrado?"])
        atual = g2.restaurar_ultimo()
        self.assertEqual((atual.id, atual.modo, atual.titulo), (aventura.id, "mestre", "Tumba antiga"))
        self.assertEqual(atual.estado["estado_combate"], "Jogador PV 11/15 | Goblin PV 7/7 CA 15")
        self.assertEqual(atual.estado["cenario"], "Masmorra nas Ruínas de uma Tumba Antiga")
        self.assertEqual([(m.ordem, m.papel, m.tipo) for m in g2.mensagens(aventura.id)],
                         [(1, "assistant", "fala"), (2, "user", "fala"), (3, "sistema", "aviso")])
        self.assertEqual(g2.historico_para_llm(aventura.id), [
            {"role": "assistant", "content": "Você vê um corredor escuro. O que você faz?"},
            {"role": "user", "content": "Ataco o goblin"},
        ])
        resposta = g2.mensagens(regras.id)[1]
        self.assertEqual(resposta.extras["fontes"], "Core | Player's Handbook (2024)")

        # a conversa continua de onde parou, com a numeração certa
        nova = g2.registrar(aventura.id, "assistant", "O goblin cai.")
        self.assertEqual(nova.ordem, 4)
        g2.fechar()

        g3 = GerenciadorDeChats.abrir()
        self.assertEqual(len(g3.mensagens(aventura.id)), 4)
        g3.fechar()

    def test_primeira_execucao_sem_chats(self):
        g = GerenciadorDeChats.abrir()
        self.addCleanup(g.fechar)
        self.assertEqual(g.listar(), [])
        self.assertIsNone(g.restaurar_ultimo())
        self.assertIsNotNone(g.novo_chat())


if __name__ == "__main__":
    unittest.main()