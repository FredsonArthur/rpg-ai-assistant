"""Erros do domínio da aplicação."""


class RPGAssistantError(Exception):
    """Classe base dos erros do assistente."""


class OllamaError(RPGAssistantError):
    """Falha ao se comunicar com o Ollama (serviço fora do ar, modelo não baixado etc.)."""


class BancoDeDadosError(RPGAssistantError):
    """O banco de chats não pôde ser aberto ou está incompatível (corrompido ou de uma versão mais nova)."""


class BaseVaziaError(RPGAssistantError):
    """A base vetorial ainda não existe: os livros precisam ser indexados."""


class ChatNaoEncontrado(RPGAssistantError):
    """O chat pedido não existe (por exemplo, foi excluído)."""


class ModoJaDefinidoError(RPGAssistantError):
    """Cada chat tem um modo fixo: ele não pode mudar depois de escolhido."""