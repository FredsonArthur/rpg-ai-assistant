"""
Serviço do Ollama
-----------------
Verifica se o servidor local do Ollama está no ar e, se não estiver, tenta iniciá-lo.
"""

import logging
import socket
import subprocess
import time

logger = logging.getLogger(__name__)

HOST = "127.0.0.1"
PORTA = 11434  # porta padrão do Ollama


def ollama_ativo(host: str = HOST, porta: int = PORTA, timeout: float = 0.5) -> bool:
    """Indica se há algo aceitando conexões na porta do Ollama."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, porta)) == 0


def iniciar_ollama(aguardar: float = 15.0, host: str = HOST, porta: int = PORTA) -> bool:
    """
    Garante que o Ollama esteja no ar. Se não estiver, executa 'ollama serve' em segundo plano
    e espera (até `aguardar` segundos) a porta abrir. Retorna True se o serviço ficou disponível.
    """
    if ollama_ativo(host, porta):
        return True

    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
    except Exception as e:  # ex.: Ollama não instalado
        logger.warning("Não foi possível iniciar o Ollama automaticamente: %s", e)
        return False

    limite = time.monotonic() + aguardar
    while time.monotonic() < limite:
        if ollama_ativo(host, porta):
            return True
        time.sleep(0.3)
    return False