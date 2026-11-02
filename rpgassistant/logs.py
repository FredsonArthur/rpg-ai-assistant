"""Configuração de logs."""

import logging
import sys

_BIBLIOTECAS_RUIDOSAS = ("httpx", "httpcore", "chromadb", "sentence_transformers", "urllib3")


def _saida_em_utf8() -> None:
    """Evita UnicodeEncodeError em consoles que não usam UTF-8 (comum no Windows): o que não couber vira "?"."""
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def configurar_logs(nivel: int = logging.INFO) -> None:
    """Liga os logs no terminal e silencia o excesso de mensagens das bibliotecas."""
    _saida_em_utf8()
    logging.basicConfig(level=nivel, format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    for nome in _BIBLIOTECAS_RUIDOSAS:
        logging.getLogger(nome).setLevel(logging.WARNING)