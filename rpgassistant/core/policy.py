"""
Política "só os livros"
-----------------------
O Assistente só responde com o que está nos livros indexados. Há duas barreiras:

1. Barreira de relevância (antes do modelo): se o melhor trecho encontrado não for parecido o bastante
   com a pergunta, a resposta é a recusa padrão, sem nem chamar o modelo.
2. Barreira do prompt (depois da busca): o modelo escreve apenas NAO_ENCONTRADO quando o contexto não
   traz a resposta, e esse código troca a palavra pela recusa padrão.
"""

from __future__ import annotations

import re
from typing import Optional

from rpgassistant.core.modos import normalizar

SENTINELA = "NAO_ENCONTRADO"
RECUSA = "Não consigo responder isso: não encontrei o assunto nos livros que tenho."


def avaliar_relevancia(melhor_similaridade: Optional[float], minimo: float) -> bool:
    """Indica se o melhor trecho é relevante o bastante para a pergunta ser respondida."""
    return melhor_similaridade is not None and melhor_similaridade >= minimo


def motivo_da_recusa(melhor_similaridade: Optional[float], minimo: float) -> str:
    """Texto técnico (exibido nas métricas) explicando por que o modelo nem foi chamado."""
    if melhor_similaridade is None:
        return "Recusado sem chamar o modelo: nenhum trecho encontrado nos livros."
    return (f"Recusado sem chamar o modelo: o melhor trecho tem similaridade {melhor_similaridade:.2f}, "
            f"abaixo do mínimo de {minimo:.2f}.")


def _canonico(texto: str) -> str:
    """Forma comparável do texto: sem acentos, maiúsculas, com espaços e hifens virando sublinhado."""
    return re.sub(r"[\s\-]+", "_", normalizar(texto).strip()).upper()


def eh_recusa_do_modelo(texto: str) -> bool:
    """O modelo respondeu NAO_ENCONTRADO (aceita 'Não encontrado', 'NAO ENCONTRADO.' etc.)."""
    return _canonico(texto).lstrip("_").startswith(SENTINELA)


def texto_visivel(texto_bruto: str) -> str:
    """
    Texto a exibir enquanto a resposta chega em streaming: esconde a sentinela, inclusive quando ela
    ainda está sendo escrita pela metade, para o usuário não ver "NAO_ENC" aparecendo.
    """
    candidato = _canonico(texto_bruto).lstrip("_")
    if candidato and (SENTINELA.startswith(candidato) or candidato.startswith(SENTINELA)):
        return ""
    return texto_bruto