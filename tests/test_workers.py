"""
Testes das threads da interface (rpgassistant/ui/workers.py)
-------------------------------------------------------------
Usam o Qt falso de tests/qt_falso.py: nele, `thread.start()` executa `run()` na hora e de forma
síncrona, então não é preciso esperar nem abrir janela, e o resultado é previsível.

Aqui se confere o que a janela recebe pelo sinal `falhou` quando o turno dá errado.
"""

import unittest

from rpgassistant.errors import ChatNaoEncontrado, OllamaError
from tests import qt_falso


def setUpModule():
    # Coloca o Qt falso no lugar do PySide6 antes de importar rpgassistant.ui.workers.
    qt_falso.instalar()


def tearDownModule():
    # Devolve os módulos originais, para não afetar os outros arquivos de teste.
    qt_falso.remover()


class FalhasDoTurnoTest(unittest.TestCase):
    def falhas(self, erro: Exception) -> list:
        """Roda um turno cuja ação levanta `erro` e devolve as mensagens emitidas pelo sinal `falhou`."""
        # Importado aqui, e não no topo, porque só pode ser carregado depois de qt_falso.instalar().
        from rpgassistant.ui.workers import TurnoThread

        def acao():
            raise erro

        mensagens = []
        thread = TurnoThread(acao)
        thread.falhou.connect(mensagens.append)  # guarda cada mensagem de erro que a janela receberia
        thread.start()  # no Qt falso, roda tudo agora, sem thread de verdade
        return mensagens

    def test_erro_do_ollama_mostra_a_mensagem_dele(self):
        """Comportamento que já existia e não pode mudar: a mensagem do OllamaError vai direto ao usuário."""
        self.assertEqual(self.falhas(OllamaError("Ollama fora do ar")), ["Ollama fora do ar"])

    def test_erro_do_dominio_nao_vira_erro_inesperado(self):
        """O ponto principal do passo 1: outros erros do app (aqui, chat excluído) também mostram a própria mensagem."""
        self.assertEqual(self.falhas(ChatNaoEncontrado("O chat 7 não existe.")), ["O chat 7 não existe."])

    def test_biblioteca_faltando_explica_como_instalar(self):
        """ImportError tem tratamento próprio: cita o pacote que falta e o comando para instalar."""
        mensagens = self.falhas(ImportError("sem módulo", name="langchain_chroma"))
        self.assertIn("langchain_chroma", mensagens[0])
        self.assertIn("pip install -r requirements.txt", mensagens[0])

    def test_erro_de_verdade_continua_sendo_inesperado(self):
        """Falhas que o app não previu (bugs) continuam avisando como "Erro inesperado"."""
        mensagens = self.falhas(RuntimeError("bug"))
        self.assertEqual(len(mensagens), 1)
        self.assertTrue(mensagens[0].startswith("Erro inesperado"))


if __name__ == "__main__":
    unittest.main()