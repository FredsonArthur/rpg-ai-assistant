"""
Comunicação com o LLM local (Ollama)
------------------------------------
Todas as chamadas ao modelo passam por aqui: resposta inteira (`chat_llm`) ou em streaming
(`chat_llm_stream`). O modelo e a janela de contexto vêm da configuração, e qualquer falha de
comunicação vira `OllamaError`, para que a interface decida como mostrá-la.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, Iterator, List

from rpgassistant import config
from rpgassistant.errors import OllamaError

logger = logging.getLogger(__name__)

Mensagens = List[Dict[str, str]]


def _ollama_chat(**kwargs: Any) -> Any:
    """Chama o Ollama. A biblioteca só é importada aqui, o que mantém o resto do código testável sem ela."""
    import ollama
    return ollama.chat(**kwargs)


def _erro_ollama(e: Exception) -> OllamaError:
    """Monta o erro padrão para falhas de comunicação com o Ollama."""
    modelo = config.settings.ollama_model
    return OllamaError(
        f"Não foi possível usar o Ollama: {e}. Verifique se o serviço está rodando "
        f"('ollama serve') e se o modelo foi baixado ('ollama pull {modelo}')."
    )


def _opcoes(temperature: float, **options: Any) -> Dict[str, Any]:
    return {"num_ctx": config.settings.ollama_num_ctx, "temperature": temperature, **options}


def chat_llm(messages: Mensagens, temperature: float, **options: Any) -> Any:
    """
    Faz uma chamada ao Ollama e devolve a resposta inteira.
    Levanta OllamaError se o serviço ou o modelo não estiverem disponíveis.
    """
    try:
        return _ollama_chat(model=config.settings.ollama_model, messages=messages,
                            options=_opcoes(temperature, **options))
    except Exception as e:
        logger.warning("Falha na chamada ao Ollama: %s", e)
        raise _erro_ollama(e) from e


class RespostaEmStream:
    """
    Resposta da LLM que chega aos poucos (streaming). Iterando `tokens()`, cada pedaço de texto
    é entregue assim que o modelo o gera; ao final, `texto` guarda a resposta completa e
    `prompt_tokens`/`completion_tokens` guardam as métricas de uso.
    Falhas durante a geração levantam OllamaError.
    """

    def __init__(self, fonte: Iterable[Any]) -> None:
        self._fonte = fonte
        self.texto = ""
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def tokens(self) -> Iterator[str]:
        try:
            for chunk in self._fonte:
                parte = chunk['message']['content']
                if parte:
                    self.texto += parte
                    yield parte
                if chunk.get('done'):
                    self.prompt_tokens = chunk.get('prompt_eval_count', 0) or 0
                    self.completion_tokens = chunk.get('eval_count', 0) or 0
        except OllamaError:
            raise
        except Exception as e:
            logger.warning("Falha durante o streaming do Ollama: %s", e)
            raise _erro_ollama(e) from e


def chat_llm_stream(messages: Mensagens, temperature: float, **options: Any) -> RespostaEmStream:
    """Como o `chat_llm`, mas devolve a resposta em streaming (ver `RespostaEmStream`)."""
    try:
        fonte = _ollama_chat(model=config.settings.ollama_model, messages=messages,
                             options=_opcoes(temperature, **options), stream=True)
    except Exception as e:
        logger.warning("Falha ao abrir o streaming do Ollama: %s", e)
        raise _erro_ollama(e) from e
    return RespostaEmStream(fonte)