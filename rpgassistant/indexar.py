"""
Indexação dos livros
--------------------
Lê os livros de data/rulebooks e recria a base vetorial em data/vectordb.

Uso:  python -m rpgassistant.indexar
"""

import sys

from rpgassistant import config
from rpgassistant.logs import configurar_logs


def main() -> int:
    configurar_logs()
    config.settings.garantir_pastas()

    from rpgassistant.services.rag import build_vector_store
    return 0 if build_vector_store() is not None else 1


if __name__ == "__main__":
    sys.exit(main())