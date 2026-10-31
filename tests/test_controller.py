import unittest

from rpgassistant.core import controller as ctl
from rpgassistant.core import policy
from rpgassistant.core.chats import GerenciadorDeChats
from rpgassistant.core.controller import ControladorDeChat
from rpgassistant.errors import ModoJaDefinidoError, OllamaError
from rpgassistant.modes import jogador, mestre
from rpgassistant.services import prompts
from rpgassistant.storage.database import Database
from rpgassistant.storage.repository import RepositorioChats
from tests.helpers import AGARRADO, CENA, FEEDBACK, VALIDA, BaseTeste, OllamaFalso, RelogioFalso, modelo, pedacos, resposta

def executar(turno):
    """Faz o que a janela faz: consome o streaming e grava a resposta."""
    partes = list(turno.tokens())
    return partes, turno.concluir()


class ControladorBase(BaseTeste):
    def setUp(self):
        super().setUp()
        self.ger = GerenciadorDeChats(RepositorioChats(Database(":memory:"), agora=RelogioFalso()))
        self.addCleanup(self.ger.fechar)
        self.c = ControladorDeChat(self.ger)
        self.falso = self.usar_ollama(OllamaFalso(responder=modelo))
        self.busca = self.usar_busca("CTX-LIVROS", "Core | PHB", similaridade=0.8)

    def novo_chat(self, primeira_mensagem=None):
        chat = self.ger.novo_chat()
        if primeira_mensagem:
            self.c.enviar(chat.id, primeira_mensagem)
        return chat.id

    def chat_mestre(self, personagem=""):
        chat_id = self.novo_chat("2")
        executar(self.c.configurar_mestre(chat_id, "Floresta Sombria e Pântano dos Goblins", personagem))
        return chat_id

    def chat_jogador(self, arquetipo="Iniciante", texto=""):
        chat_id = self.novo_chat("3")
        self.c.configurar_jogador(chat_id, "Lia", "Maga Elfa, Nível 1", arquetipo, texto)
        return chat_id

    def rotulos(self, chat_id):
        return [(m.papel, m.tipo) for m in self.ger.mensagens(chat_id)]


class PrimeiraMensagemTest(ControladorBase):
    def test_chat_novo_pede_o_modo(self):
        chat_id = self.novo_chat()
        self.assertEqual(self.c.fase(chat_id), ctl.FASE_ESCOLHER_MODO)
        boas_vindas = self.c.boas_vindas(chat_id)
        self.assertIn("Como você quer usar", boas_vindas.conteudo)
        self.assertEqual(self.rotulos(chat_id), [("assistant", "aviso")])
        self.assertIsNone(self.c.boas_vindas(chat_id))  # só uma vez
        self.assertEqual(self.ger.historico_para_llm(chat_id), [])

    def test_escolher_mestre_pelo_numero(self):
        chat_id = self.novo_chat()
        turno = self.c.enviar(chat_id, "2")
        self.assertFalse(turno.precisa_modelo)
        self.assertEqual(self.ger.repositorio.obter_chat(chat_id).modo, "mestre")
        self.assertEqual(self.c.fase(chat_id), ctl.FASE_CONFIGURAR)
        self.assertEqual(self.rotulos(chat_id), [("user", "aviso"), ("assistant", "aviso")])
        self.assertIn("Mestre", turno.salvas[-1].conteudo)
        self.assertEqual(self.falso.chamadas, [])
        self.assertEqual(self.ger.historico_para_llm(chat_id), [])

    def test_escolher_jogador_e_assistente_por_palavra_e_pedido(self):
        for texto, modo in (("jogador", "jogador"), ("quero que você seja meu mestre", "mestre"), ("assistente", "assistente"),
                            ("/jogador", "jogador"), ("quero ser o mestre", "jogador")):
            with self.subTest(texto=texto):
                chat_id = self.ger.repositorio.criar_chat().id
                self.c.enviar(chat_id, texto)
                self.assertEqual(self.ger.repositorio.obter_chat(chat_id).modo, modo)

    def test_modo_assistente_escolhido_so_pelo_nome_nao_chama_o_modelo(self):
        chat_id = self.novo_chat()
        turno = self.c.enviar(chat_id, "1")
        self.assertEqual((self.c.fase(chat_id), turno.precisa_modelo, self.falso.chamadas), (ctl.FASE_CONVERSA, False, []))

    def test_mensagem_sem_pedido_repete_as_opcoes(self):
        chat_id = self.novo_chat()
        turno = self.c.enviar(chat_id, "oi")
        self.assertIsNone(self.ger.repositorio.obter_chat(chat_id).modo)
        self.assertIn("Não entendi", turno.salvas[-1].conteudo)
        self.assertEqual(self.c.fase(chat_id), ctl.FASE_ESCOLHER_MODO)
        self.assertEqual(self.falso.chamadas, [])

    def test_ajuda_na_primeira_mensagem(self):
        chat_id = self.novo_chat()
        turno = self.c.enviar(chat_id, "/ajuda")
        self.assertIsNone(self.ger.repositorio.obter_chat(chat_id).modo)
        self.assertEqual(turno.salvas[-1].tipo, "ajuda")

    def test_pergunta_de_regras_abre_o_assistente_e_ja_e_respondida(self):
        chat_id = self.novo_chat()
        turno = self.c.enviar(chat_id, "Como funciona a condição Agarrado?")
        self.assertTrue(turno.precisa_modelo)
        chat = self.ger.repositorio.obter_chat(chat_id)
        self.assertEqual((chat.modo, chat.titulo), ("assistente", "Como funciona a condição Agarrado?"))
        partes, resp = executar(turno)
        self.assertEqual(resp.conteudo, AGARRADO)
        self.assertEqual(self.rotulos(chat_id), [("user", "fala"), ("assistant", "fala")])
        self.assertEqual(resp.extras["fontes"], "Core | PHB")
        self.assertIn("Prompt Tokens: 321 | Completion Tokens: 45", resp.extras["metricas"])
        self.assertGreater(len(partes), 1)  # chegou em pedaços

    def test_pergunta_fora_do_tema_na_primeira_mensagem(self):
        self.busca.similaridade = 0.08
        chat_id = self.novo_chat()
        turno = self.c.enviar(chat_id, "O que é uma rede neural?")
        self.assertFalse(turno.precisa_modelo)
        self.assertEqual(self.ger.repositorio.obter_chat(chat_id).modo, "assistente")
        self.assertEqual(turno.salvas[-1].conteudo, policy.RECUSA)
        self.assertTrue(turno.salvas[-1].extras["recusada"])
        self.assertIn("0.08", turno.salvas[-1].extras["metricas"])
        self.assertEqual(self.falso.chamadas, [])
        self.assertEqual(self.ger.historico_para_llm(chat_id), [])

    def test_mensagem_vazia(self):
        with self.assertRaises(ValueError):
            self.c.enviar(self.novo_chat(), "   ")


class AssistenteTest(ControladorBase):
    def chat_assistente(self):
        return self.novo_chat("1")

    def test_pergunta_e_resposta_com_memoria(self):
        chat_id = self.chat_assistente()
        executar(self.c.enviar(chat_id, "Como funciona a condição Agarrado?"))
        self.assertEqual([c for c in self.falso.chamadas if c["messages"][0]["role"] == "user"], [])  # 1ª: sem reescrita
        partes, resp = executar(self.c.enviar(chat_id, "e se eu estiver cego?"))
        reescrita = [c for c in self.falso.chamadas if c["messages"][0]["role"] == "user"]
        self.assertEqual(len(reescrita), 1)
        self.assertIn("Busca reescrita: Como funciona a condição Agarrado para um personagem cego?", resp.extras["metricas"])
        principal = [c for c in self.falso.chamadas if c.get("stream")][-1]["messages"]
        self.assertEqual([m["role"] for m in principal], ["system", "user", "assistant", "user"])
        self.assertIn("CTX-LIVROS", principal[0]["content"])
        self.assertEqual(self.busca[-1][0], "Como funciona a condição Agarrado para um personagem cego?")

    def test_pergunta_abaixo_do_limiar_e_recusada_sem_modelo(self):
        chat_id = self.chat_assistente()
        self.busca.similaridade = 0.1
        chamadas_antes = len(self.falso.chamadas)
        turno = self.c.enviar(chat_id, "Qual a capital da França?")
        self.assertFalse(turno.precisa_modelo)
        self.assertEqual(len(self.falso.chamadas), chamadas_antes)
        self.assertEqual(self.rotulos(chat_id)[-2:], [("user", "aviso"), ("assistant", "aviso")])
        self.assertEqual(self.ger.historico_para_llm(chat_id), [])  # recusas não poluem o histórico

    def test_modelo_responde_nao_encontrado(self):
        self.falso.responder = lambda kw: pedacos(["NAO_", "ENCONTRADO"]) if kw.get("stream") else resposta("NAO_ENCONTRADO")
        chat_id = self.chat_assistente()
        turno = self.c.enviar(chat_id, "Como funciona a condição Agarrado?")
        visiveis = []
        for _ in turno.tokens():
            visiveis.append(turno.texto_visivel())
        self.assertEqual(visiveis, ["", ""])  # a sentinela nunca aparece na tela
        resp = turno.concluir()
        self.assertEqual(resp.conteudo, policy.RECUSA)
        self.assertTrue(resp.extras["recusada"])
        self.assertEqual(self.rotulos(chat_id)[-2:], [("user", "aviso"), ("assistant", "aviso")])
        self.assertEqual(self.ger.historico_para_llm(chat_id), [])

    def test_ollama_fora_do_ar_desfaz_a_pergunta(self):
        chat_id = self.chat_assistente()
        antes = self.rotulos(chat_id)
        self.falso.falha = ConnectionError("fora do ar")
        with self.assertRaises(OllamaError):
            self.c.enviar(chat_id, "Como funciona a condição Agarrado?")
        self.assertEqual(self.rotulos(chat_id), antes)

    def test_falha_no_meio_do_streaming_desfaz_a_pergunta(self):
        def cai(kw):
            def gerar():
                yield {"message": {"content": "Agar"}}
                raise ConnectionError("caiu")
            return gerar()
        self.falso.responder = cai
        chat_id = self.chat_assistente()
        antes = self.rotulos(chat_id)
        turno = self.c.enviar(chat_id, "Como funciona a condição Agarrado?")
        self.assertEqual(len(self.rotulos(chat_id)), len(antes) + 1)  # a pergunta já está salva
        with self.assertRaises(OllamaError):
            list(turno.tokens())
        self.assertEqual(self.rotulos(chat_id), antes)

    def test_resposta_vazia_e_tratada_como_erro(self):
        self.falso.responder = lambda kw: pedacos([""]) if kw.get("stream") else resposta("")
        chat_id = self.chat_assistente()
        antes = self.rotulos(chat_id)
        turno = self.c.enviar(chat_id, "Como funciona a condição Agarrado?")
        list(turno.tokens())
        with self.assertRaises(OllamaError):
            turno.concluir()
        self.assertEqual(self.rotulos(chat_id), antes)

    def test_base_nao_indexada(self):
        self.busca.base_vazia = True
        chat_id = self.chat_assistente()
        turno = self.c.enviar(chat_id, "Como funciona a condição Agarrado?")
        self.assertFalse(turno.precisa_modelo)
        self.assertIn("rpgassistant.indexar", turno.salvas[-1].conteudo)
        self.assertEqual(self.ger.repositorio.obter_chat(chat_id).modo, "assistente")
        self.assertEqual(self.ger.historico_para_llm(chat_id), [])

    def test_o_titulo_vem_da_primeira_pergunta(self):
        chat_id = self.chat_assistente()
        executar(self.c.enviar(chat_id, "Como funciona a condição Agarrado?"))
        executar(self.c.enviar(chat_id, "e se eu estiver cego?"))
        self.assertEqual(self.ger.repositorio.obter_chat(chat_id).titulo, "Como funciona a condição Agarrado?")


class ComandosTest(ControladorBase):
    def test_ajuda_em_qualquer_chat(self):
        chat_id = self.novo_chat("1")
        turno = self.c.enviar(chat_id, "/ajuda")
        self.assertIn("modo fixo", turno.salvas[-1].conteudo)
        self.assertEqual(self.ger.historico_para_llm(chat_id), [])

    def test_o_modo_nao_muda_dentro_do_chat(self):
        chat_id = self.novo_chat("1")
        turno = self.c.enviar(chat_id, "/mestre")
        self.assertIn("abra um novo chat", turno.salvas[-1].conteudo)
        self.assertEqual(self.ger.repositorio.obter_chat(chat_id).modo, "assistente")
        self.assertIn("já está no modo", self.c.enviar(chat_id, "/assistente").salvas[-1].conteudo)

    def test_comando_desconhecido_mostra_a_ajuda(self):
        self.assertEqual(self.c.enviar(self.novo_chat("1"), "/xyz").salvas[-1].tipo, "ajuda")

    def test_feedback_fora_do_modo_jogador(self):
        chat_id = self.novo_chat("1")
        self.assertIn("só está disponível", self.c.enviar(chat_id, "/feedback").salvas[-1].conteudo)

    def test_mensagem_durante_a_configuracao(self):
        chat_id = self.novo_chat("2")
        turno = self.c.enviar(chat_id, "Ataco o goblin")
        self.assertFalse(turno.precisa_modelo)
        self.assertIn("configuração", turno.salvas[-1].conteudo)
        self.assertEqual(self.c.fase(chat_id), ctl.FASE_CONFIGURAR)


class MestreTest(ControladorBase):
    def test_configurar_abre_a_aventura(self):
        chat_id = self.novo_chat("2")
        turno = self.c.configurar_mestre(chat_id, "Floresta Sombria e Pântano dos Goblins", "")
        self.assertEqual(self.c.fase(chat_id), ctl.FASE_CONFIGURAR)  # só vira conversa quando o Mestre abre a cena
        partes, abertura = executar(turno)
        chat = self.ger.repositorio.obter_chat(chat_id)
        self.assertEqual(abertura.conteudo, CENA)
        self.assertEqual(chat.estado, {"cenario": "Floresta Sombria e Pântano dos Goblins",
                                       "personagem": mestre.FICHA_GENERICA, "estado_combate": ""})
        self.assertEqual(chat.titulo, "Floresta Sombria e Pântano dos Goblins")
        self.assertEqual(self.c.fase(chat_id), ctl.FASE_CONVERSA)
        self.assertEqual(self.ger.historico_para_llm(chat_id), [{"role": "assistant", "content": CENA}])
        self.assertIn("Nova aventura", [m.conteudo for m in self.ger.mensagens(chat_id) if m.tipo == "aviso"][-1])
        pedido = self.falso.chamadas[-1]["messages"][-1]["content"]
        self.assertIn("Floresta Sombria", pedido)
        self.assertIn(mestre.FICHA_GENERICA, pedido)

    def test_validacoes(self):
        chat_id = self.novo_chat("2")
        with self.assertRaises(ValueError):
            self.c.configurar_mestre(chat_id, "   ")
        with self.assertRaises(ModoJaDefinidoError):
            self.c.configurar_mestre(self.novo_chat("3"), "Tumba")
        configurado = self.chat_mestre()
        with self.assertRaisesRegex(ValueError, "já está configurado"):
            self.c.configurar_mestre(configurado, "Outro cenário")

    def test_falha_na_abertura_nao_salva_nada(self):
        chat_id = self.novo_chat("2")
        antes = self.rotulos(chat_id)
        self.falso.falha = ConnectionError("fora do ar")
        with self.assertRaises(OllamaError):
            self.c.configurar_mestre(chat_id, "Tumba")
        self.assertEqual((self.rotulos(chat_id), self.c.fase(chat_id), self.ger.estado(chat_id)), (antes, ctl.FASE_CONFIGURAR, {}))

    def test_turno_de_combate_guarda_o_estado_e_esconde_a_linha(self):
        chat_id = self.chat_mestre("Guerreiro Humano, Nível 2")
        turno = self.c.enviar(chat_id, "Ataco o goblin com minha espada")
        for _ in turno.tokens():
            self.assertNotIn("[ESTADO", turno.texto_visivel())
        resp = turno.concluir()
        self.assertEqual(resp.conteudo, "O goblin ataca! Acerta 4 de dano. O que você faz?")
        self.assertEqual(resp.extras["estado"], "Jogador PV 11/15 | Goblin PV 7/7 CA 15")
        self.assertEqual(self.ger.estado(chat_id)["estado_combate"], "Jogador PV 11/15 | Goblin PV 7/7 CA 15")
        self.assertNotIn("[ESTADO", resp.conteudo)

    def test_o_estado_e_o_historico_voltam_ao_modelo_no_turno_seguinte(self):
        chat_id = self.chat_mestre()
        executar(self.c.enviar(chat_id, "Ataco o goblin"))
        executar(self.c.enviar(chat_id, "Ataco de novo"))
        ultima = [c for c in self.falso.chamadas if c.get("stream")][-1]["messages"]
        self.assertIn("Jogador PV 11/15 | Goblin PV 7/7 CA 15", ultima[0]["content"])
        self.assertRegex(ultima[0]["content"], r"<bandeja_de_dados>\nd20: ")
        self.assertEqual([m["role"] for m in ultima[1:]], ["assistant", "user", "assistant", "user"])
        self.assertEqual(ultima[1]["content"], CENA)

    def test_o_mestre_nao_recebe_nada_de_outros_chats(self):
        regras = self.novo_chat("1")
        executar(self.c.enviar(regras, "Como funciona a condição Agarrado?"))
        chat_id = self.chat_mestre()
        executar(self.c.enviar(chat_id, "Olho ao redor"))
        mensagens = [c for c in self.falso.chamadas if c.get("stream")][-1]["messages"]
        self.assertTrue(all("Agarrado" not in m["content"] for m in mensagens))

    def test_falha_desfaz_a_acao_do_jogador(self):
        chat_id = self.chat_mestre()
        antes = self.rotulos(chat_id)
        self.falso.falha = ConnectionError("fora do ar")
        with self.assertRaises(OllamaError):
            self.c.enviar(chat_id, "Ataco o goblin")
        self.assertEqual(self.rotulos(chat_id), antes)

    def test_sem_combate_limpa_o_estado(self):
        chat_id = self.chat_mestre()
        executar(self.c.enviar(chat_id, "Ataco o goblin"))
        self.falso.responder = lambda kw: pedacos(["O goblin cai.\n", "[ESTADO] Sem combate"]) if kw.get("stream") else resposta("")
        executar(self.c.enviar(chat_id, "Ataco"))
        self.assertEqual(self.ger.estado(chat_id)["estado_combate"], "")


class JogadorTest(ControladorBase):
    def test_configurar_coloca_o_personagem_na_mesa(self):
        chat_id = self.novo_chat("3")
        self.assertEqual(self.c.fase(chat_id), ctl.FASE_CONFIGURAR)
        turno = self.c.configurar_jogador(chat_id, "Lia", "Maga Elfa, Nível 1, PV 8", "Roleplay", "")
        chat = self.ger.repositorio.obter_chat(chat_id)
        self.assertEqual(chat.estado, {"nome": "Lia", "ficha": "Lia. Maga Elfa, Nível 1, PV 8",
                                       "arquetipo": "Roleplay", "arquetipo_texto": ""})
        self.assertEqual(chat.titulo, "Lia (jogador IA)")
        self.assertEqual(self.c.fase(chat_id), ctl.FASE_CONVERSA)
        self.assertIn("Lia", turno.salvas[-1].conteudo)
        self.assertEqual(self.falso.chamadas, [])  # a saudação não usa o modelo
        self.assertEqual(self.ger.historico_para_llm(chat_id), [{"role": "assistant", "content": turno.salvas[-1].conteudo}])

    def test_nome_em_branco_e_arquetipo_invalido(self):
        chat_id = self.novo_chat("3")
        with self.assertRaises(ValueError):
            self.c.configurar_jogador(chat_id, "Lia", "Maga", "Inexistente")
        self.assertEqual(self.c.fase(chat_id), ctl.FASE_CONFIGURAR)
        self.c.configurar_jogador(chat_id, "  ", "Maga", "Tático")
        self.assertEqual(self.ger.estado(chat_id)["nome"], "Aventureiro")

    def test_turno_do_jogador(self):
        chat_id = self.chat_jogador("Roleplay")
        turno = self.c.enviar(chat_id, "Vocês entram numa taverna barulhenta.")
        partes, resp = executar(turno)
        self.assertEqual((partes, resp.conteudo), ([VALIDA], VALIDA))
        chamada = self.falso.chamadas[-1]
        self.assertFalse(chamada.get("stream", False))
        self.assertEqual(chamada["options"]["temperature"], 0.8)
        self.assertIn("Lia. Maga Elfa, Nível 1", chamada["messages"][0]["content"])
        self.assertIn(prompts.ARCHETYPES["Roleplay"], chamada["messages"][0]["content"])
        self.assertEqual(self.rotulos(chat_id)[-2:], [("user", "fala"), ("assistant", "fala")])

    def test_trocar_de_perfil_vale_no_turno_seguinte(self):
        chat_id = self.chat_jogador("Iniciante")
        executar(self.c.enviar(chat_id, "Cena 1"))
        aviso = self.c.trocar_arquetipo(chat_id, "Tático")
        self.assertEqual((aviso.papel, aviso.tipo), ("sistema", "aviso"))
        executar(self.c.enviar(chat_id, "Cena 2"))
        self.assertIn(prompts.ARCHETYPES["Tático"], self.falso.chamadas[-1]["messages"][0]["content"])
        self.assertEqual(self.falso.chamadas[-1]["options"]["temperature"], 0.3)
        self.assertGreaterEqual(len(self.falso.chamadas[-1]["messages"]), 5)  # o histórico foi mantido

    def test_trocar_perfil_so_no_modo_jogador_configurado(self):
        with self.assertRaises(ValueError):
            self.c.trocar_arquetipo(self.novo_chat("1"), "Tático")
        with self.assertRaises(ValueError):
            self.c.trocar_arquetipo(self.novo_chat("3"), "Tático")
        with self.assertRaises(ValueError):
            self.c.trocar_arquetipo(self.chat_jogador(), "Inexistente")

    def test_perfil_personalizado(self):
        chat_id = self.chat_jogador("Personalizado", "muito desconfiado e cauteloso")
        executar(self.c.enviar(chat_id, "Cena"))
        self.assertIn("muito desconfiado e cauteloso", self.falso.chamadas[-1]["messages"][0]["content"])

    def test_falha_desfaz_a_fala_do_mestre(self):
        chat_id = self.chat_jogador()
        antes = self.rotulos(chat_id)
        self.falso.falha = ConnectionError("fora do ar")
        turno = self.c.enviar(chat_id, "Cena")
        with self.assertRaises(OllamaError):
            list(turno.tokens())
        self.assertEqual(self.rotulos(chat_id), antes)

    def test_feedback_com_historico_curto(self):
        chat_id = self.chat_jogador()
        executar(self.c.enviar(chat_id, "Cena 1"))
        turno = self.c.enviar(chat_id, "/feedback")
        self.assertFalse(turno.precisa_modelo)
        self.assertEqual(turno.salvas[-1].conteudo, jogador.AVISO_HISTORICO_CURTO)

    def test_feedback_completo_fica_no_chat_mas_fora_do_historico(self):
        chat_id = self.chat_jogador()
        executar(self.c.enviar(chat_id, "Cena 1"))
        executar(self.c.enviar(chat_id, "Cena 2"))
        turno = self.c.enviar(chat_id, "/feedback")
        self.assertTrue(turno.precisa_modelo)
        _, resp = executar(turno)
        self.assertEqual((resp.papel, resp.tipo, resp.conteudo), ("sistema", "feedback", FEEDBACK))
        self.assertTrue(all("Pontos Fortes" not in m["content"] for m in self.ger.historico_para_llm(chat_id)))
        executar(self.c.enviar(chat_id, "Cena 3"))
        self.assertTrue(all("Pontos Fortes" not in m["content"] for m in self.falso.chamadas[-1]["messages"]))
        self.assertNotIn("/feedback", [m.conteudo for m in self.ger.mensagens(chat_id)])  # o comando não vira mensagem


class ReiniciarOAppTest(BaseTeste):
    """Fechar e abrir o app depois de uma aventura em andamento devolve tudo, e a conversa continua."""

    def test_aventura_continua_depois_de_reiniciar(self):
        falso = self.usar_ollama(OllamaFalso(responder=modelo))
        self.usar_busca()

        g1 = GerenciadorDeChats.abrir()
        c1 = ControladorDeChat(g1)
        chat_id = g1.novo_chat().id
        c1.boas_vindas(chat_id)
        c1.enviar(chat_id, "quero que você seja meu mestre")
        executar(c1.configurar_mestre(chat_id, "Floresta Sombria e Pântano dos Goblins", "Guerreiro Humano, Nível 2"))
        executar(c1.enviar(chat_id, "Ataco o goblin"))
        g1.fechar()

        # --- o app é fechado e aberto de novo ---
        g2 = GerenciadorDeChats.abrir()
        c2 = ControladorDeChat(g2)
        chat = g2.restaurar_ultimo()
        self.assertEqual((chat.id, chat.modo, chat.titulo), (chat_id, "mestre", "Floresta Sombria e Pântano dos Goblins"))
        self.assertEqual(c2.fase(chat_id), ctl.FASE_CONVERSA)
        self.assertEqual(g2.estado(chat_id)["estado_combate"], "Jogador PV 11/15 | Goblin PV 7/7 CA 15")

        executar(c2.enviar(chat_id, "Ataco de novo"))
        enviado = [c for c in falso.chamadas if c.get("stream")][-1]["messages"]
        self.assertIn("Jogador PV 11/15 | Goblin PV 7/7 CA 15", enviado[0]["content"])
        self.assertEqual([m["role"] for m in enviado[1:]], ["assistant", "user", "assistant", "user"])
        self.assertEqual(enviado[1]["content"], CENA)
        self.assertEqual(len([m for m in g2.mensagens(chat_id) if m.tipo == "fala"]), 5)  # abertura + 2 turnos
        g2.fechar()


if __name__ == "__main__":
    unittest.main()