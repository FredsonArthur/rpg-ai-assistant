"""
Threads da interface
--------------------
O modelo leva segundos para responder, então tudo que o chama roda fora da thread da janela. Os
resultados voltam por sinais do Qt, que entregam sempre na thread da janela.

Há duas threads:
- TurnoThread: executa um turno do ControladorDeChat (uma pergunta, uma configuração ou um feedback)
  e avisa a janela, pelos sinais, de cada etapa: mensagens salvas, texto chegando, conclusão, falha
  ou cancelamento.
- OllamaThread: garante que o servidor do Ollama esteja no ar, sem travar a abertura do app.
"""

from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtCore import QThread, Signal

from rpgassistant.core.controller import Turno
from rpgassistant.errors import RPGAssistantError
from rpgassistant.services.ollama_service import iniciar_ollama

logger = logging.getLogger(__name__)


class TurnoThread(QThread):
    """
    Executa um turno do controlador fora da thread da janela.

    Ordem dos sinais em um turno normal:
        salvas -> pedaco (várias vezes) -> concluido
    Em caso de problema, no lugar de `concluido` sai um destes:
        falhou     (houve um erro; o sinal leva a mensagem para mostrar ao usuário)
        cancelado  (o usuário apertou Parar)

    Depois de qualquer um dos três finais, o sinal `finished` do próprio QThread também é emitido.
    """

    # (mensagens que o controlador já gravou no banco, o turno ainda vai chamar o modelo?)
    salvas = Signal(object, bool)
    # Texto acumulado até agora, já pronto para exibir (sem a sentinela nem a linha [ESTADO]).
    pedaco = Signal(str)
    # A resposta final já gravada (MensagemChat), ou None se o turno não usou o modelo.
    concluido = Signal(object)
    # Mensagem de erro escrita para o usuário final.
    falhou = Signal(str)
    # O usuário interrompeu a resposta; a pergunta foi desfeita pelo controlador.
    cancelado = Signal()

    def __init__(self, acao: Callable[[], Turno], parent=None) -> None:
        """
        `acao` é uma função sem argumentos que chama o controlador e devolve o `Turno` (por exemplo,
        `lambda: controlador.enviar(chat_id, texto)`). Ela só é chamada dentro de `run`, ou seja, já
        na thread nova, porque algumas ações (como a busca nos livros) também demoram.
        """
        super().__init__(parent)
        self._acao = acao
        self._parar = False  # vira True quando o usuário pede para interromper

    def parar(self) -> None:
        """Pede para interromper; vale a partir do próximo pedaço de texto."""
        self._parar = True

    def run(self) -> None:
        """Corpo da thread: roda o turno e traduz cada desfecho em um sinal para a janela."""
        try:
            # 1. A ação monta o turno e já grava no banco o que não precisa do modelo.
            turno = self._acao()
            self.salvas.emit(turno.salvas, turno.precisa_modelo)

            # 2. Consome a resposta aos poucos, repassando à janela o texto acumulado.
            iterador = turno.tokens()
            try:
                for _ in iterador:
                    if self._parar:
                        break
                    self.pedaco.emit(turno.texto_visivel())
            finally:
                iterador.close()  # fecha a conexão com o Ollama, que para de gerar

            # 3. Desfecho: cancelamento (desfaz a pergunta) ou conclusão (grava a resposta).
            if self._parar:
                turno.cancelar()
                self.cancelado.emit()
                return
            self.concluido.emit(turno.concluir())

        # A ordem dos `except` importa: o Python usa o primeiro que combina.
        except RPGAssistantError as e:
            # Erros previstos pelo próprio app (Ollama fora do ar, chat que não existe mais, modelo
            # sem resposta...). `OllamaError` e os demais herdam desta classe, e a mensagem já foi
            # escrita para o usuário, então é mostrada como está e nada vai para o log.
            self.falhou.emit(str(e))
        except ImportError as e:
            # Uma biblioteca do requirements.txt não está instalada neste Python.
            self.falhou.emit(f"Falta instalar uma biblioteca ({e.name or e}). Rode: pip install -r requirements.txt")
        except Exception as e:
            # Qualquer outro erro é um bug de verdade: vai para o log, com o traceback, e o usuário
            # recebe um aviso. Nunca deixar a thread morrer sem avisar a janela, senão a tela ficaria
            # travada em "ocupado".
            logger.exception("Erro inesperado ao processar o turno")
            self.falhou.emit(f"Erro inesperado: {e}")


class OllamaThread(QThread):
    """Garante, em segundo plano, que o Ollama esteja no ar (inicia o servidor se for preciso)."""

    # True se o serviço está respondendo; False se não foi possível iniciá-lo.
    pronto = Signal(bool)

    def run(self) -> None:
        """Pode levar até alguns segundos (espera o servidor abrir a porta), por isso roda aqui."""
        self.pronto.emit(iniciar_ollama())