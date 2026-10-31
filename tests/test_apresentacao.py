import unittest
from datetime import datetime, timezone

from rpgassistant.core.models import Chat, MensagemChat
from rpgassistant.ui import apresentacao as ap

AGORA = datetime(2026, 10, 30, tzinfo=timezone.utc)


def msg(papel, conteudo, tipo="fala", extras=None):
    return MensagemChat(1, 1, 1, papel, conteudo, tipo, extras or {}, AGORA)


def chat(modo=None, estado=None, titulo="Novo chat"):
    return Chat(1, titulo, modo, estado or {}, AGORA, AGORA)


class DescreverMensagemTest(unittest.TestCase):
    def test_usuario(self):
        self.assertEqual(ap.descrever_mensagem(msg("user", "oi"), "assistente"), ap.Bolha("usuario", "Você", "oi"))
        self.assertEqual(ap.descrever_mensagem(msg("user", "cena"), "jogador").autor, "Você (Mestre)")

    def test_usuario_com_tipo_aviso_continua_sendo_do_usuario(self):
        self.assertEqual(ap.descrever_mensagem(msg("user", "2", "aviso"), None).estilo, "usuario")

    def test_resposta_do_assistente_com_fontes_e_metricas(self):
        bolha = ap.descrever_mensagem(msg("assistant", "Resp", extras={"fontes": "Core | PHB", "metricas": "Prompt Tokens: 7"}), "assistente")
        self.assertEqual((bolha.estilo, bolha.autor), ("assistente", "🧙 Assistente"))
        self.assertEqual(bolha.rodape, "📚 Core | PHB\nPrompt Tokens: 7")

    def test_resposta_do_mestre_com_estado_de_combate(self):
        bolha = ap.descrever_mensagem(msg("assistant", "O goblin ataca.", extras={"estado": "Jogador PV 9/15", "fontes": "Core | MM"}), "mestre")
        self.assertEqual(bolha.autor, "🗺️ Mestre")
        self.assertEqual(bolha.rodape, "⚔️ Estado do combate: Jogador PV 9/15\n📚 Core | MM")

    def test_jogador_usa_o_nome_do_personagem(self):
        self.assertEqual(ap.descrever_mensagem(msg("assistant", "x"), "jogador", "Lia").autor, "⚔️ Lia")
        self.assertEqual(ap.descrever_mensagem(msg("assistant", "x"), "jogador").autor, "⚔️ Jogador IA")

    def test_recusa(self):
        bolha = ap.descrever_mensagem(msg("assistant", "Não consigo...", "aviso", {"recusada": True, "metricas": "Recusado..."}), "assistente")
        self.assertEqual((bolha.estilo, bolha.rodape), ("recusa", "Recusado..."))

    def test_avisos_ajuda_e_feedback(self):
        self.assertEqual(ap.descrever_mensagem(msg("assistant", "Boas-vindas", "aviso"), None), ap.Bolha("aviso", "🎲 RPG AI Assistant", "Boas-vindas"))
        self.assertEqual(ap.descrever_mensagem(msg("assistant", "Comandos", "ajuda"), "assistente"), ap.Bolha("ajuda", "", "Comandos"))
        self.assertEqual(ap.descrever_mensagem(msg("sistema", "Nova aventura", "aviso"), "mestre"), ap.Bolha("aviso", "", "Nova aventura"))
        self.assertEqual(ap.descrever_mensagem(msg("sistema", "Pontos Fortes", "feedback"), "jogador"), ap.Bolha("feedback", "📝 Mentor", "Pontos Fortes"))


class ChatETelaTest(unittest.TestCase):
    def test_titulo_do_chat_na_lista(self):
        self.assertEqual(ap.titulo_do_chat(chat(None, titulo="Novo chat")), "💬  Novo chat")
        self.assertEqual(ap.titulo_do_chat(chat("assistente", titulo="Agarrar")), "🧙  Agarrar")
        self.assertEqual(ap.titulo_do_chat(chat("mestre", titulo="Tumba")), "🗺️  Tumba")
        self.assertEqual(ap.titulo_do_chat(chat("jogador", titulo="Lia")), "⚔️  Lia")

    def test_selo_do_modo(self):
        self.assertEqual(ap.selo_do_modo(None), "Escolha o modo")
        self.assertIn("Mestre", ap.selo_do_modo("mestre"))

    def test_resumo_da_sessao(self):
        self.assertIn("livros", ap.resumo_sessao(chat("assistente"), False)[0])
        self.assertEqual(ap.resumo_sessao(chat(None), False), [])
        self.assertIn("Falta configurar", ap.resumo_sessao(chat("mestre"), True)[0])
        mestre = chat("mestre", {"cenario": "Tumba", "personagem": "Guerreiro", "estado_combate": "Jogador PV 9/15"})
        self.assertEqual(ap.resumo_sessao(mestre, False), ["🏰 Tumba", "🛡️ Guerreiro", "⚔️ Jogador PV 9/15"])
        self.assertEqual(len(ap.resumo_sessao(chat("mestre", {"cenario": "T", "personagem": "G", "estado_combate": ""}), False)), 2)
        self.assertEqual(ap.resumo_sessao(chat("jogador", {"ficha": "Lia. Maga"}), False), ["🛡️ Lia. Maga"])
        self.assertIn("Falta definir", ap.resumo_sessao(chat("jogador"), True)[0])

    def test_markdown_preserva_as_quebras_de_linha(self):
        self.assertEqual(ap.markdown_para_exibir("a\nb"), "a  \nb")
        self.assertEqual(ap.markdown_para_exibir("a\n\nb"), "a\n\nb")          # parágrafos continuam iguais
        self.assertEqual(ap.markdown_para_exibir("- um\n- dois"), "- um  \n- dois")
        self.assertEqual(ap.markdown_para_exibir("sem quebra"), "sem quebra")

    def test_bolha_de_erro(self):
        self.assertEqual(ap.bolha_de_erro("Falhou"), ap.Bolha("erro", "", "⚠️ Falhou"))


if __name__ == "__main__":
    unittest.main()