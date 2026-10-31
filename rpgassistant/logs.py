"""Configuração de logs."""

import logging

_BIBLIOTECAS_RUIDOSAS = ("httpx", "httpcore", "chromadb", "sentence_transformers", "urllib3")


def configurar_logs(nivel: int = logging.INFO) -> None:
    """Liga os logs no terminal e silencia o excesso de mensagens das bibliotecas."""
    logging.basicConfig(level=nivel, format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    for nome in _BIBLIOTECAS_RUIDOSAS:
        logging.getLogger(nome).setLevel(logging.WARNING)