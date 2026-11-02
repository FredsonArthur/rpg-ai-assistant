"""
Verificação do ambiente
-----------------------
Confere, antes de abrir o app, a versão do Python e se as bibliotecas necessárias estão instaladas no
Python que está executando o programa. Assim, um problema de instalação vira uma mensagem clara
(com o comando para resolver), e não um erro solto no meio do uso.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import sys
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

VERSAO_MINIMA = (3, 10)
VERSAO_RECOMENDADA = "3.12"
PRIMEIRA_VERSAO_MUITO_NOVA = (3, 14)

# (módulo importado, pacote do pip)
DEPENDENCIAS: List[Tuple[str, str]] = [
    ("PySide6", "PySide6"),
    ("ollama", "ollama"),
    ("langchain_core", "langchain-core"),
    ("langchain_community", "langchain-community"),
    ("langchain_text_splitters", "langchain-text-splitters"),
    ("langchain_huggingface", "langchain-huggingface"),
    ("langchain_chroma", "langchain-chroma"),
    ("sentence_transformers", "sentence-transformers"),
    ("chromadb", "chromadb"),
    ("pypdf", "pypdf"),
]

COMANDO_INSTALAR = "pip install -r requirements.txt"


@dataclass(frozen=True)
class Problema:
    gravidade: str   # "erro" impede de abrir o app; "aviso" só informa
    texto: str


def versao_instalada(pacote: str) -> Optional[str]:
    """Versão do pacote no Python atual, ou None se não estiver instalado."""
    try:
        return importlib.metadata.version(pacote)
    except importlib.metadata.PackageNotFoundError:
        return None


def verificar_python(versao: tuple = tuple(sys.version_info[:3])) -> List[Problema]:
    texto = ".".join(str(n) for n in versao[:3])
    if tuple(versao[:2]) < VERSAO_MINIMA:
        return [Problema("erro", f"O Python {texto} é antigo demais: use o Python {VERSAO_RECOMENDADA}.")]
    if tuple(versao[:2]) >= PRIMEIRA_VERSAO_MUITO_NOVA:
        return [Problema(
            "aviso",
            f"O Python {texto} é muito novo: algumas bibliotecas ainda não têm pacote pronto para ele e a "
            f"instalação pode falhar pedindo um compilador C++. Se isso acontecer, use o Python {VERSAO_RECOMENDADA}.",
        )]
    return []


def dependencias_ausentes(achar: Callable = importlib.util.find_spec) -> List[str]:
    """Pacotes do pip que não estão instalados."""
    return [pacote for modulo, pacote in DEPENDENCIAS if achar(modulo) is None]


def verificar_ambiente(versao: tuple = tuple(sys.version_info[:3]), achar: Callable = importlib.util.find_spec) -> List[Problema]:
    problemas = verificar_python(versao)
    ausentes = dependencias_ausentes(achar)
    if ausentes:
        problemas.append(Problema(
            "erro",
            f"Faltam bibliotecas neste Python ({sys.executable}): {', '.join(ausentes)}.\n"
            f"Com o ambiente virtual ativado, rode:  {COMANDO_INSTALAR}\n"
            "Se você abriu o projeto pelo VSCode, confirme que o interpretador escolhido é o do ambiente virtual "
            "(Ctrl+Shift+P, \"Python: Select Interpreter\").",
        ))
    return problemas