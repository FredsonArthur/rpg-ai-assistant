"""
Threads da interface
--------------------
O modelo leva segundos para responder, então tudo que o chama roda fora da thread da janela. Os
resultados voltam por sinais do Qt, que entregam sempre na thread da janela.
"""

from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtCore import QThread, Signal

from rpgassistant.core.controller import Turno
from rpgassistant.errors import OllamaError
from rpgassistant.services.ollama_service import iniciar_ollama

logger = logging.getLogger(__name__)


class TurnoThread(QThread):
    """Executa um turno do controlador: devolve as mensagens salvas, o texto aos poucos e o resultado final."""

    salvas = Signal(object, bool)   # (mensagens já salvas, o turno ainda vai usar o modelo?)
    pedaco = Signal(str)            # texto acumulado, já pronto para exibir
    concluido = Signal(object)      # a resposta salva (ou None)
    falhou = Signal(str)            # mensagem de erro para o usuário
    cancelado = Signal()

    def __init__(self, acao: Callable[[], Turno], parent=None) -> None:
        super().__init__(parent)
        self._acao = acao
        self._parar = False

    def parar(self) -> None:
        """Pede para interromper; vale a partir do próximo pedaço de texto."""
        self._parar = True

    def run(self) -> None:
        try:
            turno = self._acao()
            self.salvas.emit(turno.salvas, turno.precisa_modelo)
            iterador = turno.tokens()
            try:
                for _ in iterador:
                    if self._parar:
                        break
                    self.pedaco.emit(turno.texto_visivel())
            finally:
                iterador.close()  # fecha a conexão com o Ollama, que para de gerar
            if self._parar:
                turno.cancelar()
                self.cancelado.emit()
                return
            self.concluido.emit(turno.concluir())
        except OllamaError as e:
            self.falhou.emit(str(e))
        except ImportError as e:
            self.falhou.emit(f"Falta instalar uma biblioteca ({e.name or e}). Rode: pip install -r requirements.txt")
        except Exception as e:  # nunca deixar a thread morrer sem avisar a janela
            logger.exception("Erro inesperado ao processar o turno")
            self.falhou.emit(f"Erro inesperado: {e}")


class OllamaThread(QThread):
    """Garante, em segundo plano, que o Ollama esteja no ar."""

    pronto = Signal(bool)

    def run(self) -> None:
        self.pronto.emit(iniciar_ollama())