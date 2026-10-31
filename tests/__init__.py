"""Testes automatizados. Rodar com:  python -m unittest discover -s tests -t .   (ou: pytest)"""

import logging

# Os testes provocam falhas de propósito; sem isso, os avisos de log poluiriam a saída.
logging.disable(logging.CRITICAL)