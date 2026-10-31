"""
Testes da lógica da janela com o Qt falso (tests/qt_falso.py): rodam em qualquer máquina, sem tela.
Conferem o fluxo (chats, modos, streaming, erros, parar, reabrir), não a aparência.
"""

import sys
import unittest
from unittest import mock

from rpgassistant.core.chats import GerenciadorDeChats
from rpgassistant.core.controller import ControladorDeChat
from rpgassistant.storage.database import Database
from rpgassistant.storage.repository import RepositorioChats
from tests import qt_falso
from tests.helpers import BaseTeste, OllamaFalso, RelogioFalso, modelo, pedacos, resposta


def setUpModule():
    qt_falso.instalar()


def tearDownModule():
    qt_falso.remover()


def texto(bolha):
    return bolha._texto.text()


def widgets():
    return sys.modules["PySide6.QtWidgets"]


class JanelaBase(BaseTeste):
    def construir(self, gerenciador=None):
        self.ger = gerenciador or GerenciadorDeChats(RepositorioChats(Database(":memory:"), agora=RelogioFalso()))
        self.ctrl = ControladorDeChat(self.ger)
        qt_falso.QShortcut.registrados.clear()
        widgets().QDialog.resultado = 1
        widgets().QMessageBox.resposta = widgets().QMessageBox.StandardButton.Yes
        widgets().QMessageBox.chamadas.clear()
        widgets().QInputDialog.retorno = ("", False)
        widgets().QMenu.escolher = None
        from rpgassistant.ui.janela import JanelaPrincipal
        self.janela = JanelaPrincipal(self.ctrl, iniciar_ollama=False)
        return self.janela

    def setUp(self):
        super().setUp()
        self.falso = self.usar_ollama(OllamaFalso(responder=modelo))
        self.busca = self.usar_busca("CTX-LIVROS", "Core | PHB", similaridade=0.8)
        self.construir()
        self.addCleanup(self.ger.fechar)

    def enviar(self, mensagem):
        self.janela.entrada.setPlainText(mensagem)
        self.janela.btn_enviar.clicked.emit()

    def bolhas(self):
        return self.janela.area.bolhas

    def estilos(self):
        return [b.property("estilo") for b in self.bolhas()]


class AbrirTest(JanelaBase):
    def test_chat_novo_mostra_as_boas_vindas(self):
        j = self.janela
        self.assertEqual(j.lista.count(), 1)
        self.assertEqual(j.lista.item(0).text(), "💬  Novo chat")
        self.assertEqual(j.area.quantidade, 1)
        self.assertIn("Como você quer usar", texto(self.bolhas()[0]))
        self.assertEqual(self.estilos(), ["aviso"])
        self.assertEqual(j.selo.text(), "Escolha o modo")
        self.assertFalse(j.painel.isVisible())
        self.assertEqual(j.btn_enviar.text(), "Enviar")
        self.assertFalse(j.ocupado)
        self.assertIn("llama3", j.statusBar().mensagem)

    def test_atalhos(self):
        sequencias = [a.sequencia for a in qt_falso.QShortcut.registrados]
        self.assertEqual(sorted(sequencias), ["Ctrl+N", "F2"])

    def test_ollama_em_segundo_plano(self):
        from rpgassistant.ui import workers
        for ativo, trecho in ((True, "Ollama pronto"), (False, "não está rodando")):
            with self.subTest(ativo=ativo), mock.patch.object(workers, "iniciar_ollama", return_value=ativo):
                from rpgassistant.ui.janela import JanelaPrincipal
                janela = JanelaPrincipal(self.ctrl, iniciar_ollama=True)
                self.assertIn(trecho, janela.statusBar().mensagem)


class AssistenteTest(JanelaBase):
    def test_pergunta_e_resposta_com_fontes(self):
        self.enviar("Como funciona a condição Agarrado?")
        self.assertEqual(self.estilos(), ["aviso", "usuario", "assistente"])
        resposta_ia = self.bolhas()[-1]
        self.assertIn("Agarrado", texto(resposta_ia))
        self.assertIn("Core | PHB", resposta_ia._rodape.text())
        self.assertIn("Prompt Tokens", resposta_ia._rodape.text())
        j = self.janela
        self.assertEqual(j.entrada.toPlainText(), "")
        self.assertFalse(j.ocupado)
        self.assertEqual(j.btn_enviar.text(), "Enviar")
        self.assertEqual(j.selo.text(), "🧙 Assistente")
        self.assertEqual(j.titulo.text(), "Como funciona a condição Agarrado?")
        self.assertEqual(j.lista.item(0).text(), "🧙  Como funciona a condição Agarrado?")
        self.assertTrue(j.painel.isVisible())
        self.assertIn("livros", j.lbl_sessao.text())

    def test_enter_envia_e_shift_enter_nao(self):
        j = self.janela
        j.entrada.setPlainText("Como funciona a condição Agarrado?")
        evento = type("Evento", (), {"key": lambda s: 16777220, "modifiers": lambda s: 0, "texto": ""})()
        j.entrada.keyPressEvent(evento)
        self.assertEqual(self.estilos(), ["aviso", "usuario", "assistente"])
        j.entrada.setPlainText("e se eu estiver cego?")
        shift = type("Evento", (), {"key": lambda s: 16777220, "modifiers": lambda s: 2, "texto": "\n"})()
        j.entrada.keyPressEvent(shift)
        self.assertEqual(len(self.bolhas()), 3)  # Shift+Enter só quebra a linha
        self.assertTrue(j.entrada.toPlainText().endswith("\n"))

    def test_mensagem_vazia_e_ignorada(self):
        self.enviar("   ")
        self.assertEqual(len(self.bolhas()), 1)
        self.assertEqual(self.falso.chamadas, [])

    def test_recusa_fora_do_tema(self):
        self.busca.similaridade = 0.05
        self.enviar("Qual a capital da França?")
        self.assertEqual(self.estilos(), ["aviso", "usuario", "recusa"])
        self.assertIn("Não consigo responder isso", texto(self.bolhas()[-1]))
        self.assertEqual(self.falso.chamadas, [])

    def test_ajuda(self):
        self.enviar("/ajuda")
        self.assertEqual(self.estilos(), ["aviso", "usuario", "ajuda"])

    def test_primeira_mensagem_sem_pedido_repete_as_opcoes(self):
        self.enviar("oi")
        self.assertIn("Não entendi", texto(self.bolhas()[-1]))
        self.assertEqual(self.janela.selo.text(), "Escolha o modo")

    def test_ollama_fora_do_ar_mostra_o_erro_e_devolve_o_texto(self):
        antes = len(self.ger.mensagens(self.ger.chat_atual.id))
        self.falso.falha = ConnectionError("fora do ar")
        self.enviar("Como funciona a condição Agarrado?")
        self.assertEqual(self.estilos(), ["aviso", "erro"])
        self.assertIn("ollama pull llama3", texto(self.bolhas()[-1]))
        self.assertEqual(self.janela.entrada.toPlainText(), "Como funciona a condição Agarrado?")
        self.assertEqual(len(self.ger.mensagens(self.ger.chat_atual.id)), antes)
        self.assertFalse(self.janela.ocupado)
        self.assertEqual(self.janela.btn_enviar.text(), "Enviar")

    def test_parar_a_geracao_desfaz_a_pergunta(self):
        def responder(kwargs):
            if not kwargs.get("stream"):
                return resposta("x")

            def gerar():
                yield {"message": {"content": "Agar"}}
                self.janela._thread_atual.parar()  # o usuário aperta "Parar" no meio da resposta
                yield {"message": {"content": "rado"}}
            return gerar()

        self.falso.responder = responder
        antes = len(self.ger.mensagens(self.ger.chat_atual.id))
        self.enviar("Como funciona a condição Agarrado?")
        self.assertEqual(self.estilos(), ["aviso", "erro"])
        self.assertIn("interrompida", texto(self.bolhas()[-1]))
        self.assertEqual(self.janela.entrada.toPlainText(), "Como funciona a condição Agarrado?")
        self.assertEqual(len(self.ger.mensagens(self.ger.chat_atual.id)), antes)
        self.assertFalse(self.janela.ocupado)

    def test_streaming_atualiza_a_bolha(self):
        j = self.janela
        j._autor_stream, j._estilo_stream = "🧙 Assistente", "assistente"
        j._ao_salvar([], True)
        bolha = j._bolha_stream
        self.assertEqual(texto(bolha), "…")
        j._ao_pedaco("Olá")
        self.assertEqual(texto(bolha), "Olá ▌")
        j._ao_pedaco("")
        self.assertEqual(texto(bolha), "…")

    def test_modelo_diz_nao_encontrado(self):
        self.falso.responder = lambda kw: pedacos(["NAO_", "ENCONTRADO"]) if kw.get("stream") else resposta("NAO_ENCONTRADO")
        self.enviar("Como funciona a condição Agarrado?")
        self.assertEqual(self.estilos(), ["aviso", "usuario", "recusa"])

    def test_controles_ficam_travados_enquanto_gera(self):
        j = self.janela
        j._definir_ocupado(True)
        self.assertEqual((j.lista.isEnabled(), j.btn_novo.isEnabled(), j.painel.isEnabled()), (False, False, False))
        self.assertEqual(j.btn_enviar.text(), "⏹  Parar")
        j._enviar_texto("ignorada")
        j._novo_chat()
        self.assertEqual((len(self.bolhas()), self.ger.listar().__len__()), (1, 1))
        j._definir_ocupado(False)
        self.assertTrue(j.lista.isEnabled())


class MestreTest(JanelaBase):
    def test_escolher_mestre_abre_a_configuracao_e_a_aventura(self):
        self.enviar("2")
        j = self.janela
        self.assertEqual(j.selo.text(), "🗺️ Mestre (a IA narra)")
        self.assertIn("corredor escuro", texto(self.bolhas()[-1]))
        self.assertEqual(self.bolhas()[-1]._autor.text(), "🗺️ Mestre")
        estado = self.ger.estado(self.ger.chat_atual.id)
        self.assertEqual(estado["cenario"], "Masmorra nas Ruínas de uma Tumba Antiga")
        self.assertTrue(j.painel.isVisible())
        self.assertIn("🏰 Masmorra", j.lbl_sessao.text())
        self.assertFalse(j.btn_config.isVisible())
        self.assertEqual(j.lista.item(0).text(), "🗺️  Masmorra nas Ruínas de uma Tumba Antiga")

    def test_cancelar_a_configuracao_deixa_o_botao_configurar(self):
        widgets().QDialog.resultado = 0
        self.enviar("2")
        j = self.janela
        self.assertTrue(j.btn_config.isVisible())
        self.assertIn("Falta configurar", j.lbl_sessao.text())
        widgets().QDialog.resultado = 1
        j.btn_config.clicked.emit()
        self.assertFalse(j.btn_config.isVisible())
        self.assertIn("corredor escuro", texto(self.bolhas()[-1]))

    def test_falha_ao_abrir_a_aventura_mantem_a_configuracao_pendente(self):
        self.falso.falha = ConnectionError("fora do ar")
        self.enviar("/mestre")
        j = self.janela
        self.assertEqual(self.estilos()[-1], "erro")
        self.assertTrue(j.btn_config.isVisible())
        self.falso.falha = None
        j.btn_config.clicked.emit()
        self.assertFalse(j.btn_config.isVisible())

    def test_combate_mostra_o_estado(self):
        self.enviar("2")
        self.enviar("Ataco o goblin com minha espada")
        ultima = self.bolhas()[-1]
        self.assertNotIn("[ESTADO", texto(ultima))
        self.assertIn("Estado do combate: Jogador PV 11/15", ultima._rodape.text())
        self.assertIn("⚔️ Jogador PV 11/15", self.janela.lbl_sessao.text())


class JogadorTest(JanelaBase):
    def test_configurar_trocar_perfil_e_jogar(self):
        self.enviar("3")
        j = self.janela
        self.assertEqual(j.selo.text(), "⚔️ Jogador (a IA joga)")
        self.assertTrue(j.controles_jogador.isVisible())
        self.assertEqual(j.combo_perfil.currentText(), "Iniciante")
        self.assertIn("Lia", texto(self.bolhas()[-1]))

        self.enviar("Vocês entram numa taverna barulhenta.")
        resposta_ia = self.bolhas()[-1]
        self.assertEqual(resposta_ia._autor.text(), "⚔️ Lia")
        self.assertIn("[Ação]", texto(resposta_ia))
        self.assertEqual(self.bolhas()[-2]._autor.text(), "Você (Mestre)")

        j.combo_perfil.setCurrentText("Tático")
        chat_id = self.ger.chat_atual.id
        self.assertEqual(self.ger.estado(chat_id)["arquetipo"], "Tático")
        self.assertIn("Perfil de jogador alterado para Tático", texto(self.bolhas()[-1]))
        self.assertEqual(j.combo_perfil.currentText(), "Tático")

    def test_perfil_personalizado(self):
        self.enviar("/jogador")
        j = self.janela
        j.combo_perfil.setCurrentText("Personalizado")
        self.assertTrue(j.edit_perfil.isEnabled())
        j.edit_perfil.setText("muito desconfiado")
        j.edit_perfil.editingFinished.emit()
        estado = self.ger.estado(self.ger.chat_atual.id)
        self.assertEqual((estado["arquetipo"], estado["arquetipo_texto"]), ("Personalizado", "muito desconfiado"))

    def test_campo_de_perfil_sem_mudanca_nao_gera_aviso(self):
        self.enviar("3")
        antes = len(self.bolhas())
        self.janela.edit_perfil.editingFinished.emit()
        self.assertEqual(len(self.bolhas()), antes)

    def test_feedback(self):
        self.enviar("3")
        j = self.janela
        self.enviar("Cena 1")
        j.btn_feedback.clicked.emit()
        self.assertEqual(self.estilos()[-1], "ajuda")
        self.assertIn("muito curta", texto(self.bolhas()[-1]))
        self.enviar("Cena 2")
        j.btn_feedback.clicked.emit()
        self.assertEqual(self.estilos()[-1], "feedback")
        self.assertEqual(self.bolhas()[-1]._autor.text(), "📝 Mentor")
        self.assertIn("Pontos Fortes", texto(self.bolhas()[-1]))

    def test_dialogo_cancelado(self):
        widgets().QDialog.resultado = 0
        self.enviar("3")
        self.assertTrue(self.janela.btn_config.isVisible())
        self.assertFalse(self.janela.controles_jogador.isVisible())


class VariosChatsTest(JanelaBase):
    def test_novo_chat_e_alternar(self):
        self.enviar("Como funciona a condição Agarrado?")
        j = self.janela
        j._novo_chat()
        self.assertEqual(j.lista.count(), 2)
        self.assertEqual(j.lista.item(0).text(), "💬  Novo chat")
        self.assertEqual(len(self.bolhas()), 1)

        j.lista.setCurrentRow(1)  # volta ao primeiro chat
        self.assertEqual(self.estilos(), ["aviso", "usuario", "assistente"])
        self.assertEqual(j.titulo.text(), "Como funciona a condição Agarrado?")
        j.lista.setCurrentRow(0)
        self.assertEqual(len(self.bolhas()), 1)

    def test_novo_chat_reaproveita_o_vazio(self):
        self.janela._novo_chat()
        self.janela._novo_chat()
        self.assertEqual(self.janela.lista.count(), 1)

    def test_atalho_ctrl_n(self):
        self.enviar("Como funciona a condição Agarrado?")
        atalho = next(a for a in qt_falso.QShortcut.registrados if a.sequencia == "Ctrl+N")
        atalho.activated.emit()
        self.assertEqual(self.janela.lista.count(), 2)

    def test_renomear(self):
        j = self.janela
        widgets().QInputDialog.retorno = ("Minha campanha", True)
        next(a for a in qt_falso.QShortcut.registrados if a.sequencia == "F2").activated.emit()
        self.assertEqual((j.titulo.text(), j.lista.item(0).text()), ("Minha campanha", "💬  Minha campanha"))
        widgets().QInputDialog.retorno = ("   ", True)
        j._renomear()
        self.assertEqual(j.titulo.text(), "Minha campanha")
        self.assertEqual(widgets().QMessageBox.chamadas[-1][0], "warning")
        widgets().QInputDialog.retorno = ("Outro", False)  # cancelou
        j._renomear()
        self.assertEqual(j.titulo.text(), "Minha campanha")

    def test_excluir_pelo_menu_de_contexto(self):
        self.enviar("Como funciona a condição Agarrado?")
        j = self.janela
        j._novo_chat()
        widgets().QMenu.escolher = "Excluir"
        j.lista.customContextMenuRequested.emit(1)  # botão direito no 2º item
        self.assertEqual(j.lista.count(), 1)
        self.assertEqual(j.lista.item(0).text(), "💬  Novo chat")

    def test_excluir_pede_confirmacao(self):
        self.enviar("Como funciona a condição Agarrado?")
        widgets().QMessageBox.resposta = widgets().QMessageBox.StandardButton.No
        self.janela._excluir()
        self.assertEqual(self.janela.lista.count(), 1)
        self.assertEqual(len(self.bolhas()), 3)

    def test_excluir_o_unico_chat_cria_um_novo(self):
        self.enviar("Como funciona a condição Agarrado?")
        self.janela._excluir()
        self.assertEqual(self.janela.lista.count(), 1)
        self.assertEqual(self.janela.lista.item(0).text(), "💬  Novo chat")
        self.assertEqual(len(self.bolhas()), 1)

    def test_renomear_com_menu_de_contexto(self):
        widgets().QMenu.escolher = "Renomear"
        widgets().QInputDialog.retorno = ("Por menu", True)
        self.janela.lista.customContextMenuRequested.emit(0)
        self.assertEqual(self.janela.titulo.text(), "Por menu")


class ReabrirTest(BaseTeste):
    """Fechar a janela e abrir de novo, com o banco em arquivo, traz tudo de volta."""

    def test_conversa_volta_depois_de_fechar(self):
        from rpgassistant.ui.janela import JanelaPrincipal
        self.usar_ollama(OllamaFalso(responder=modelo))
        self.usar_busca("CTX-LIVROS", "Core | PHB", similaridade=0.8)
        widgets().QDialog.resultado = 1

        ger1 = GerenciadorDeChats.abrir()
        janela = JanelaPrincipal(ControladorDeChat(ger1), iniciar_ollama=False)
        janela.entrada.setPlainText("Como funciona a condição Agarrado?")
        janela.btn_enviar.clicked.emit()
        janela.entrada.setPlainText("2")
        janela._novo_chat()
        janela.entrada.setPlainText("2")
        janela.btn_enviar.clicked.emit()
        janela.entrada.setPlainText("Ataco o goblin")
        janela.btn_enviar.clicked.emit()
        janela.close()

        # --- o app abre de novo ---
        ger2 = GerenciadorDeChats.abrir()
        self.addCleanup(ger2.fechar)
        nova = JanelaPrincipal(ControladorDeChat(ger2), iniciar_ollama=False)
        self.assertEqual(nova.lista.count(), 2)
        self.assertEqual(nova.selo.text(), "🗺️ Mestre (a IA narra)")           # abre no chat usado por último
        self.assertIn("⚔️ Jogador PV 11/15", nova.lbl_sessao.text())             # estado de combate preservado
        self.assertIn("goblin ataca", texto(nova.area.bolhas[-1]))
        nova.lista.setCurrentRow(1)
        self.assertEqual(nova.titulo.text(), "Como funciona a condição Agarrado?")
        self.assertIn("Agarrado", texto(nova.area.bolhas[-1]))


if __name__ == "__main__":
    unittest.main()