"""
Configurações globais
---------------------
Reúne caminhos, parâmetros do RAG e do modelo em um objeto tipado e imutável (`settings`).
Nada acontece ao importar este módulo: as pastas só são criadas quando `garantir_pastas()` é chamado.

Variáveis de ambiente:
- OLLAMA_MODEL    modelo do Ollama (padrão: llama3)
- OLLAMA_NUM_CTX  janela de contexto em tokens (padrão: 8192)
- RPG_DATA_DIR    pasta de dados (padrão: <projeto>/data)
- RPG_RELEVANCIA_MINIMA  limiar do Assistente "só os livros" (0 a 1; veja python -m rpgassistant.calibrar)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Mapping

BASE_DIR = Path(__file__).resolve().parent.parent

# Temperatura por perfil de jogador (UC07). Valores iniciais, a ajustar nos testes.
_TEMPERATURAS_ARQUETIPO: Dict[str, float] = {
    "Iniciante": 0.5,       # previsível, focado em tirar dúvidas
    "Tático": 0.3,          # preciso e objetivo
    "Roleplay": 0.8,        # criativo, rico em falas
    "Personalizado": 0.6,   # perfil escrito pelo usuário
}


def _inteiro_do_ambiente(nome: str, padrao: int) -> int:
    valor = os.getenv(nome)
    if valor is None or not valor.strip():
        return padrao
    try:
        return int(valor)
    except ValueError as e:
        raise ValueError(f"A variável de ambiente {nome} precisa ser um número inteiro (recebi {valor!r}).") from e


def _decimal_do_ambiente(nome: str, padrao: float) -> float:
    valor = os.getenv(nome)
    if valor is None or not valor.strip():
        return padrao
    try:
        numero = float(valor.replace(",", "."))
    except ValueError as e:
        raise ValueError(f"A variável de ambiente {nome} precisa ser um número (recebi {valor!r}).") from e
    if not 0.0 <= numero <= 1.0:
        raise ValueError(f"A variável de ambiente {nome} precisa estar entre 0 e 1 (recebi {valor!r}).")
    return numero


@dataclass(frozen=True)
class Config:
    """Configuração do assistente. Para testes, crie uma nova com `dataclasses.replace`."""

    data_dir: Path = BASE_DIR / "data"

    # RAG. ATENÇÃO: mudar embedding_model, chunk_size ou chunk_overlap deixa a base vetorial antiga
    # incompatível; depois de mudar qualquer um deles, rode a indexação de novo (python -m rpgassistant.indexar).
    # Valores iniciais, ainda não validados com testes de recuperação.
    chunk_size: int = 1500          # tamanho do trecho, em caracteres
    chunk_overlap: int = 300        # sobreposição entre trechos vizinhos, em caracteres
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    top_k_assistente: int = 8       # trechos recuperados para o Assistente
    top_k_mestre: int = 3           # trechos recuperados para o Mestre
    # Assistente "só os livros": se o melhor trecho encontrado tiver similaridade (de 0 a 1) abaixo deste
    # limiar, a pergunta é recusada sem chamar o modelo. 0 desliga a barreira. O valor padrão é apenas um
    # palpite: calibre com os seus livros usando  python -m rpgassistant.calibrar
    relevancia_minima: float = 0.30

    # Quantidade de mensagens recentes enviadas ao modelo (Mestre e Jogador)
    history_window: int = 10

    # Ollama. O padrão do Ollama para a janela de contexto é baixo (2048 a 4096 tokens) e, quando o
    # prompt estoura, o início (o prompt do sistema) é cortado. O Llama 3 suporta até 8192.
    ollama_model: str = "llama3"
    ollama_num_ctx: int = 8192

    # Temperaturas (valores iniciais, a ajustar nos testes)
    temperatura_assistente: float = 0.3   # regras: precisão e pouca invenção
    temperatura_mestre: float = 0.7       # narrativa: mais criatividade
    temperatura_feedback: float = 0.4     # feedback pedagógico (UC09): analítico
    temperatura_arquetipos: Mapping[str, float] = field(default_factory=lambda: dict(_TEMPERATURAS_ARQUETIPO))
    temperatura_arquetipo_padrao: float = 0.5

    @property
    def rulebooks_dir(self) -> Path:
        return self.data_dir / "rulebooks"

    @property
    def vectordb_dir(self) -> Path:
        return self.data_dir / "vectordb"

    @property
    def chats_db(self) -> Path:
        return self.data_dir / "chats.db"

    def temperatura_do_arquetipo(self, arquetipo: str) -> float:
        return self.temperatura_arquetipos.get(arquetipo, self.temperatura_arquetipo_padrao)

    def garantir_pastas(self) -> None:
        """Cria a pasta de dados e a pasta dos livros, se ainda não existirem."""
        self.rulebooks_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> "Config":
        """Monta a configuração padrão, aplicando as variáveis de ambiente."""
        pasta = os.getenv("RPG_DATA_DIR")
        return cls(
            data_dir=Path(pasta).expanduser() if pasta else BASE_DIR / "data",
            ollama_model=os.getenv("OLLAMA_MODEL") or "llama3",
            ollama_num_ctx=_inteiro_do_ambiente("OLLAMA_NUM_CTX", 8192),
            relevancia_minima=_decimal_do_ambiente("RPG_RELEVANCIA_MINIMA", 0.30),
        )


settings = Config.from_env()