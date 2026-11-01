"""
RAG: livros, trechos, embeddings e busca
----------------------------------------
Pipeline de recuperação de contexto do assistente:
1. Leitura dos livros (PDF e Markdown), com busca recursiva em subpastas.
2. Divisão do texto em trechos (chunking).
3. Embeddings multilíngues (HuggingFace) e base vetorial local (ChromaDB).
4. Busca por similaridade, com o rótulo do livro (Core ou Suplemento) em cada trecho.

As bibliotecas pesadas (LangChain, Chroma, sentence-transformers) só são importadas quando
usadas, para a aplicação abrir rápido e o restante do código ser testável sem elas.
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, List, Optional, Tuple

from rpgassistant import config
from rpgassistant.core.historico import Historico
from rpgassistant.errors import BaseVaziaError
from rpgassistant.services import llm
from rpgassistant.services.prompts import REWRITE_PROMPT

if TYPE_CHECKING:  # só para as anotações de tipo
    from langchain_chroma import Chroma
    from langchain_core.documents import Document
    from langchain_huggingface import HuggingFaceEmbeddings

logger = logging.getLogger(__name__)

# Quantos trechos são indexados por vez (permite mostrar o progresso da indexação)
BATCH_INDEXACAO = 256

# Instâncias carregadas sob demanda e reaproveitadas entre as perguntas
# (carregar o modelo de embeddings e abrir o Chroma a cada pergunta é lento).
_embeddings: Optional[Any] = None
_vector_store: Optional[Any] = None


def get_embeddings() -> "HuggingFaceEmbeddings":
    """Retorna o modelo de embeddings multilíngue, carregando-o só na primeira vez."""
    global _embeddings
    if _embeddings is None:
        from langchain_huggingface import HuggingFaceEmbeddings
        _embeddings = HuggingFaceEmbeddings(
            model_name=config.settings.embedding_model,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
    return _embeddings


def _relatar_arquivos_lidos(documents: "List[Document]") -> None:
    """Informa quantos arquivos foram lidos e quais foram pulados, para uma falha não passar despercebida."""
    lidos = {os.path.abspath(d.metadata.get("source", "")) for d in documents}
    for extensao in ("pdf", "md"):
        esperados = sorted(os.path.abspath(str(p)) for p in config.settings.rulebooks_dir.rglob(f"*.{extensao}"))
        if not esperados:
            continue
        faltando = [os.path.basename(p) for p in esperados if p not in lidos]
        logger.info("Arquivos .%s lidos: %d de %d", extensao, len(esperados) - len(faltando), len(esperados))
        for nome in faltando:
            logger.warning("Não foi possível ler: %s", nome)


def build_vector_store() -> "Optional[Chroma]":
    """
    Lê os livros (PDF e Markdown) da pasta de dados e subpastas, divide em trechos, gera os embeddings
    e recria a base vetorial no ChromaDB. Devolve None se não houver livros para indexar.
    """
    global _vector_store
    from langchain_chroma import Chroma
    from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader, TextLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    cfg = config.settings
    logger.info("Lendo documentos em: %s", cfg.rulebooks_dir)

    if not cfg.rulebooks_dir.exists():
        cfg.rulebooks_dir.mkdir(parents=True, exist_ok=True)
        logger.warning("Pasta %s criada. Adicione os livros em PDF ou Markdown nela.", cfg.rulebooks_dir)
        return None

    # silent_errors=True: um arquivo com problema é pulado, em vez de derrubar a leitura toda.
    pdf_loader = DirectoryLoader(
        str(cfg.rulebooks_dir), glob="**/*.pdf", loader_cls=PyPDFLoader, recursive=True, silent_errors=True
    )
    md_loader = DirectoryLoader(
        str(cfg.rulebooks_dir), glob="**/*.md", loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},  # evita falha de encoding (ex.: cp1252 no Windows)
        recursive=True, silent_errors=True
    )

    documents: "List[Document]" = []
    for nome, loader in (("PDF", pdf_loader), ("Markdown", md_loader)):
        try:
            documents.extend(loader.load())
        except Exception as e:
            logger.info("Nenhum arquivo %s carregado ou aviso: %s", nome, e)

    if not documents:
        logger.warning("Nenhum arquivo PDF ou Markdown encontrado na pasta de regras.")
        return None

    _relatar_arquivos_lidos(documents)

    logger.info("Dividindo %d documento(s) em trechos...", len(documents))
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=cfg.chunk_size,
        chunk_overlap=cfg.chunk_overlap,
        separators=["\n\n", "\n", " ", ""]
    )
    chunks = text_splitter.split_documents(documents)
    logger.info("Total de trechos gerados: %d", len(chunks))

    logger.info("Carregando o modelo de embeddings...")
    embeddings = get_embeddings()

    # Recria a base do zero: o Chroma só acrescenta à coleção existente, então reindexar sem limpar
    # duplicaria todos os trechos. (Feito só depois de o modelo de embeddings carregar, para não
    # apagar a base antiga se algo falhar antes.)
    if cfg.vectordb_dir.exists():
        shutil.rmtree(cfg.vectordb_dir)
    cfg.vectordb_dir.mkdir(parents=True, exist_ok=True)

    vector_store = Chroma(persist_directory=str(cfg.vectordb_dir), embedding_function=embeddings)
    total = len(chunks)
    logger.info("Gerando embeddings e gravando no ChromaDB (pode demorar)...")
    for inicio in range(0, total, BATCH_INDEXACAO):
        vector_store.add_documents(chunks[inicio:inicio + BATCH_INDEXACAO])
        logger.info("%d/%d trechos indexados", min(inicio + BATCH_INDEXACAO, total), total)

    _vector_store = vector_store
    logger.info("Base vetorial construída com sucesso!")
    return vector_store


def load_vector_store() -> "Optional[Chroma]":
    """
    Retorna a base vetorial persistida no disco, abrindo-a só na primeira vez.
    Se a base ainda não existe, devolve None (sem carregar o modelo de embeddings).
    """
    global _vector_store
    if _vector_store is None:
        pasta = config.settings.vectordb_dir
        if pasta.exists() and any(pasta.iterdir()):
            from langchain_chroma import Chroma
            _vector_store = Chroma(persist_directory=str(pasta), embedding_function=get_embeddings())
    return _vector_store


def rotulo_fonte(source: str) -> str:
    """
    Monta o rótulo de um livro a partir do caminho do arquivo, indicando se é Core ou suplemento.
    Ex.: .../rulebooks/core/Player's Handbook (2024).md -> "Core | Player's Handbook (2024)"
    """
    partes = source.replace("\\", "/").split("/")
    nome = os.path.splitext(partes[-1])[0] or "Livro"
    if "rulebooks" in partes:
        indice = len(partes) - 1 - partes[::-1].index("rulebooks")  # última ocorrência
        subpasta = partes[indice + 1] if indice + 1 < len(partes) - 1 else ""
        tipo = "Core" if subpasta == "core" else "Suplemento"
    else:
        tipo = "Livro"
    return f"{tipo} | {nome}"


@dataclass(frozen=True)
class ResultadoBusca:
    """Resultado de uma busca nos livros: o contexto montado, as fontes e quão relevante foi o melhor trecho."""

    contexto: str
    fontes: str
    melhor_similaridade: Optional[float]  # de 0 a 1 (None se nenhum trecho foi encontrado)
    trechos: int


def distancia_para_similaridade(distancia: float, espaco: str = "l2") -> float:
    """
    Converte a distância devolvida pelo Chroma em similaridade (1 = idêntico, 0 = sem relação).
    Os embeddings são normalizados, então, no espaço L2 (o padrão do Chroma), d² = 2 (1 - cos).
    """
    if espaco == "cosine":
        return 1.0 - distancia
    return 1.0 - (distancia ** 2) / 2.0


def _espaco_da_base(db: Any) -> str:
    try:
        return (db._collection.metadata or {}).get("hnsw:space", "l2")
    except Exception:
        return "l2"


def buscar_contexto(query: str, k: Optional[int] = None) -> ResultadoBusca:
    """
    Busca por similaridade semântica nos livros. Devolve os trechos mais relevantes (cada um com o
    rótulo do livro), as fontes e a similaridade do melhor trecho. `k` padrão: top_k_assistente.
    Levanta BaseVaziaError se os livros ainda não foram indexados.
    """
    k = k if k is not None else config.settings.top_k_assistente
    db = load_vector_store()
    if not db:
        raise BaseVaziaError("A base de livros ainda não foi indexada. Rode: python -m rpgassistant.indexar")

    pares = db.similarity_search_with_score(query, k=k)
    if not pares:
        return ResultadoBusca("Nenhum trecho relevante encontrado.", "Desconhecido", None, 0)

    espaco = _espaco_da_base(db)
    context_chunks: List[str] = []
    fontes_encontradas: List[str] = []  # lista (e não set) para manter a ordem de relevância
    melhor = max(distancia_para_similaridade(distancia, espaco) for _, distancia in pares)

    for doc, _ in pares:
        rotulo = rotulo_fonte(doc.metadata.get('source', ''))
        page = doc.metadata.get('page')  # só existe em PDFs; a página 0 também conta
        if page is not None:
            rotulo += f" - pág. {page + 1}"

        if rotulo not in fontes_encontradas:
            fontes_encontradas.append(rotulo)

        context_chunks.append(f"📖 [Fonte: {rotulo}]\n{doc.page_content.strip()}")

    return ResultadoBusca("\n\n---\n\n".join(context_chunks), ", ".join(fontes_encontradas), melhor, len(pares))


def recuperar_contexto(query: str, k: Optional[int] = None) -> Tuple[str, str]:
    """
    Como `buscar_contexto`, mas devolve só (contexto, fontes) e nunca levanta erro: sem base, o próprio
    contexto avisa. Usada pelo Mestre, que não recusa perguntas.
    """
    try:
        resultado = buscar_contexto(query, k)
    except BaseVaziaError:
        return "⚠️ Base vetorial não inicializada. Execute a indexação dos manuais.", "Nenhuma fonte"
    return resultado.contexto, resultado.fontes


def reescrever_pergunta(question: str, chat_history: Historico) -> str:
    """
    Transforma uma pergunta que depende da conversa ("e se eu estiver cego?") em uma pergunta
    autônoma, para que a busca vetorial encontre os trechos certos. Sem histórico, ou se algo
    falhar, devolve a pergunta original.
    """
    if not chat_history:
        return question

    transcricao = "\n".join(
        f"{'Usuário' if msg['role'] == 'user' else 'Assistente'}: {msg['content'][:500]}"
        for msg in chat_history[-4:]
    )
    prompt = REWRITE_PROMPT.format(history=transcricao, question=question)

    try:
        response = llm.chat_llm([{"role": "user", "content": prompt}], temperature=0, num_predict=100)
        linhas = response['message']['content'].strip().strip('"').splitlines()
        reescrita = linhas[0].strip().strip('"') if linhas else ""
        if 3 <= len(reescrita) <= 300:
            return reescrita
    except Exception as e:
        # Sem reescrita a busca ainda funciona; a falha real aparecerá na chamada principal.
        logger.debug("Reescrita da pergunta ignorada: %s", e)
    return question