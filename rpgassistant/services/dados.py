"""
Dados de verdade
----------------
Modelos de linguagem não sorteiam números: eles escolhem um valor que "parece" aleatório.
Para o Mestre virtual, o sorteio é feito aqui, em Python, e o resultado é entregue ao modelo
numa "bandeja de dados" que ele precisa usar em vez de inventar rolagens.
"""

import random
from typing import Optional

# Quantos valores de cada dado a bandeja traz por turno
_BANDEJA = ((20, 4), (12, 2), (10, 2), (8, 3), (6, 4), (4, 2))


def bandeja_de_dados(rng: Optional[random.Random] = None) -> str:
    """
    Sorteia uma bandeja nova de dados para o turno do Mestre.
    Ex.: "d20: 14, 3, 19, 8 | d12: 5, 11 | d10: 2, 7 | d8: 6, 1, 4 | d6: 3, 5, 2, 6 | d4: 1, 4"
    """
    rng = rng or random
    partes = []
    for faces, quantidade in _BANDEJA:
        valores = ", ".join(str(rng.randint(1, faces)) for _ in range(quantidade))
        partes.append(f"d{faces}: {valores}")
    return " | ".join(partes)