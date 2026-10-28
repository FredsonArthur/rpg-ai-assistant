"""
Módulo de Mecanismo de RAG (Retrieval-Augmented Generation)
------------------------------------------------------------
Este script gerencia todo o pipeline de RAG do assistente de RPG:
1. Carregamento dos livros de regras/lore (PDF e Markdown), com busca recursiva em subpastas.
2. Divisão do texto em fragmentos (chunking).
3. Geração de vetores com embeddings multilíngues (HuggingFace).
4. Persistência e busca semântica em base vetorial local (ChromaDB).
5. Resposta via Ollama (Llama 3), com memória da conversa e reescrita da pergunta para a busca.

Autor: Projeto RPG AI Assistant
Data: 2026
"""

import os
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

from langchain_community.document_loaders import PyPDFLoader, TextLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
import ollama

from src.prompt_templates import SYSTEM_PROMPT, REWRITE_PROMPT
from src.config import (
    RULEBOOKS_DIR,
    VECTORDB_DIR,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    EMBEDDING_MODEL_NAME,
    TOP_K_RESULTS,
    OLLAMA_MODEL,
    OLLAMA_NUM_CTX,
    HISTORY_WINDOW,
    TEMPERATURE_ASSISTANT,
)

# Quantos trechos são indexados por vez (permite mostrar progresso na indexação)
BATCH_INDEXACAO = 256

# Instâncias carregadas sob demanda e reaproveitadas entre as perguntas
# (carregar o modelo de embeddings e abrir o Chroma a cada pergunta é lento).
_embeddings: Optional[HuggingFaceEmbeddings] = None
_vector_store: Optional[Chroma] = None


class OllamaError(Exception):
    """Falha ao se comunicar com o Ollama (serviço fora do ar, modelo não baixado etc.)."""


def get_embeddings() -> HuggingFaceEmbeddings:
    """
    Retorna o modelo de embeddings multilíngue do HuggingFace, carregando-o só na primeira vez.
    """
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL_NAME,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
    return _embeddings


def _relatar_arquivos_lidos(documents: List[Document]) -> None:
    """
    Mostra quantos arquivos foram lidos e quais foram pulados, para que uma falha de leitura
    não passe despercebida.
    """
    lidos = {os.path.abspath(d.metadata.get("source", "")) for d in documents}
    for extensao in ("pdf", "md"):
        esperados = sorted(os.path.abspath(str(p)) for p in Path(RULEBOOKS_DIR).rglob(f"*.{extensao}"))
        if not esperados:
            continue
        faltando = [os.path.basename(p) for p in esperados if p not in lidos]
        print(f"📚 [RAG Engine] Arquivos .{extensao} lidos: {len(esperados) - len(faltando)} de {len(esperados)}")
        for nome in faltando:
            print(f"   ⚠️ Não foi possível ler: {nome}")


def build_vector_store() -> Optional[Chroma]:
    """
    Processa os livros (PDF e Markdown) da pasta de dados e subpastas, aplica o chunking,
    gera os embeddings e recria a base vetorial no ChromaDB.
    """
    global _vector_store
    print(f"📄 [RAG Engine] Lendo documentos em: {RULEBOOKS_DIR}...")

    if not os.path.exists(RULEBOOKS_DIR):
        os.makedirs(RULEBOOKS_DIR, exist_ok=True)
        print(f"⚠️ Diretório {RULEBOOKS_DIR} criado. Adicione os livros em PDF ou Markdown nele.")
        return None

    # silent_errors=True: um arquivo com problema é pulado, em vez de derrubar a leitura toda.
    pdf_loader = DirectoryLoader(
        RULEBOOKS_DIR,
        glob="**/*.pdf",
        loader_cls=PyPDFLoader,
        recursive=True,
        silent_errors=True
    )
    md_loader = DirectoryLoader(
        RULEBOOKS_DIR,
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},  # evita falha de encoding (ex: cp1252 no Windows)
        recursive=True,
        silent_errors=True
    )

    documents: List[Document] = []
    for nome, loader in (("PDF", pdf_loader), ("Markdown", md_loader)):
        try:
            documents.extend(loader.load())
        except Exception as e:
            print(f"ℹ️ Nenhum arquivo {nome} carregado ou aviso: {e}")

    if not documents:
        print("⚠️ [RAG Engine] Nenhum arquivo PDF ou Markdown encontrado na pasta de regras.")
        return None

    _relatar_arquivos_lidos(documents)

    print(f"✂️ [RAG Engine] Dividindo {len(documents)} documento(s) em chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""]
    )

    chunks: List[Document] = text_splitter.split_documents(documents)
    print(f"🧩 [RAG Engine] Total de chunks gerados: {len(chunks)}")

    print("💾 [RAG Engine] Carregando o modelo de embeddings...")
    embeddings = get_embeddings()

    # Recria a base do zero: o Chroma só acrescenta à coleção existente, então reindexar sem
    # limpar duplicaria todos os chunks. (Feito só depois de o modelo de embeddings carregar,
    # para não apagar a base antiga se algo falhar antes.)
    if os.path.exists(VECTORDB_DIR):
        shutil.rmtree(VECTORDB_DIR)
    os.makedirs(VECTORDB_DIR, exist_ok=True)

    vector_store = Chroma(persist_directory=VECTORDB_DIR, embedding_function=embeddings)
    total = len(chunks)
    print("💾 [RAG Engine] Gerando embeddings e gravando no ChromaDB (pode demorar)...")
    for inicio in range(0, total, BATCH_INDEXACAO):
        vector_store.add_documents(chunks[inicio:inicio + BATCH_INDEXACAO])
        print(f"   ... {min(inicio + BATCH_INDEXACAO, total)}/{total} trechos indexados")

    _vector_store = vector_store
    print("✅ [RAG Engine] Base Vetorial construída com sucesso!")
    return vector_store


def load_vector_store() -> Optional[Chroma]:
    """
    Retorna a base vetorial persistida no disco, abrindo-a só na primeira vez.
    Se a base ainda não existe, devolve None (sem carregar o modelo de embeddings).
    """
    global _vector_store
    if _vector_store is None:
        if os.path.exists(VECTORDB_DIR) and os.listdir(VECTORDB_DIR):
            _vector_store = Chroma(
                persist_directory=VECTORDB_DIR,
                embedding_function=get_embeddings()
            )
    return _vector_store


def _rotulo_fonte(source: str) -> str:
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


def recuperar_contexto(query: str, k: int = TOP_K_RESULTS) -> Tuple[str, str]:
    """
    Realiza a busca por similaridade semântica retornando os trechos mais relevantes
    (cada um com o rótulo do livro) e a lista de fontes correspondente.
    """
    db = load_vector_store()
    if not db:
        return "⚠️ Base vetorial não inicializada. Execute a indexação dos manuais.", "Nenhuma fonte"

    results: List[Document] = db.similarity_search(query, k=k)
    if not results:
        return "Nenhum trecho relevante encontrado.", "Desconhecido"

    context_chunks = []
    fontes_encontradas = []  # lista (e não set) para manter a ordem de relevância

    for doc in results:
        rotulo = _rotulo_fonte(doc.metadata.get('source', ''))
        page = doc.metadata.get('page')  # só existe em PDFs; a página 0 também conta
        if page is not None:
            rotulo += f" - pág. {page + 1}"

        if rotulo not in fontes_encontradas:
            fontes_encontradas.append(rotulo)

        context_chunks.append(f"📖 [Fonte: {rotulo}]\n{doc.page_content.strip()}")

    texto_contexto = "\n\n---\n\n".join(context_chunks)
    return texto_contexto, ", ".join(fontes_encontradas)


def _erro_ollama(e: Exception) -> OllamaError:
    """Monta o erro padrão para falhas de comunicação com o Ollama."""
    return OllamaError(
        f"Não foi possível usar o Ollama: {e}. Verifique se o serviço está rodando "
        f"('ollama serve') e se o modelo foi baixado ('ollama pull {OLLAMA_MODEL}')."
    )


def _opcoes(temperature: float, **options) -> dict:
    return {"num_ctx": OLLAMA_NUM_CTX, "temperature": temperature, **options}


def chat_llm(messages: list, temperature: float, **options) -> dict:
    """
    Chamada única ao Ollama, usada por todos os modos do assistente (modelo e janela de
    contexto vêm da config). Levanta OllamaError se o serviço ou o modelo não estiverem
    disponíveis; quem chama decide como mostrar o erro.
    """
    try:
        return ollama.chat(model=OLLAMA_MODEL, messages=messages, options=_opcoes(temperature, **options))
    except Exception as e:
        raise _erro_ollama(e) from e


class RespostaEmStream:
    """
    Resposta da LLM que chega aos poucos (streaming). Iterando `tokens()`, cada pedaço de texto
    é entregue assim que o modelo o gera; ao final, `texto` guarda a resposta completa e
    `prompt_tokens`/`completion_tokens` guardam as métricas de uso.
    Falhas durante a geração levantam OllamaError.
    """

    def __init__(self, fonte):
        self._fonte = fonte
        self.texto = ""
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def tokens(self):
        try:
            for chunk in self._fonte:
                parte = chunk['message']['content']
                if parte:
                    self.texto += parte
                    yield parte
                if chunk.get('done'):
                    self.prompt_tokens = chunk.get('prompt_eval_count', 0) or 0
                    self.completion_tokens = chunk.get('eval_count', 0) or 0
        except OllamaError:
            raise
        except Exception as e:
            raise _erro_ollama(e) from e


def chat_llm_stream(messages: list, temperature: float, **options) -> RespostaEmStream:
    """Como o chat_llm, mas devolve a resposta em streaming (ver RespostaEmStream)."""
    try:
        fonte = ollama.chat(
            model=OLLAMA_MODEL, messages=messages, options=_opcoes(temperature, **options), stream=True
        )
    except Exception as e:
        raise _erro_ollama(e) from e
    return RespostaEmStream(fonte)


def reescrever_pergunta(question: str, chat_history: list) -> str:
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
        response = chat_llm([{"role": "user", "content": prompt}], temperature=0, num_predict=100)
        linhas = response['message']['content'].strip().strip('"').splitlines()
        reescrita = linhas[0].strip().strip('"') if linhas else ""
        if 3 <= len(reescrita) <= 300:
            return reescrita
    except Exception:
        pass  # sem reescrita a busca ainda funciona; a falha real aparecerá na chamada principal
    return question


def formatar_metricas(prompt_tokens: int, completion_tokens: int, consulta: str, pergunta: str) -> str:
    """Texto de métricas exibido ao usuário (tokens usados e, se houve, a busca reescrita)."""
    metricas = f"Prompt Tokens: {prompt_tokens} | Completion Tokens: {completion_tokens}"
    if consulta != pergunta:
        metricas += f" | Busca reescrita: {consulta}"
    return metricas


def _preparar_consulta(question: str, chat_history: Optional[list],
                       prompt_template: str) -> Tuple[list, str, str]:
    """
    Passos comuns da consulta RAG: reescreve a pergunta (usando o histórico), busca os trechos
    nos livros e monta as mensagens (prompt do sistema + histórico recente + pergunta).
    Retorna (mensagens, fontes, consulta usada na busca).
    """
    chat_history = chat_history or []

    consulta = reescrever_pergunta(question, chat_history)
    contexto, fontes = recuperar_contexto(consulta, k=TOP_K_RESULTS)

    system_prompt = prompt_template.format(context=contexto, question=question)
    messages = [{"role": "system", "content": system_prompt}]
    for msg in chat_history[-HISTORY_WINDOW:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": question})
    return messages, fontes, consulta


def query_rag(question: str, chat_history: Optional[list] = None,
              prompt_template: str = SYSTEM_PROMPT) -> Tuple[str, str, str]:
    """
    Consulta principal do assistente, com a resposta inteira de uma vez.

    chat_history: mensagens anteriores ({"role", "content"}), SEM a pergunta atual.
    Retorna (resposta, fontes, métricas). Levanta OllamaError se o Ollama falhar.
    """
    messages, fontes, consulta = _preparar_consulta(question, chat_history, prompt_template)
    response = chat_llm(messages, temperature=TEMPERATURE_ASSISTANT)

    metricas = formatar_metricas(
        response.get('prompt_eval_count', 0), response.get('eval_count', 0), consulta, question
    )
    return response['message']['content'], fontes, metricas


def query_rag_stream(question: str, chat_history: Optional[list] = None,
                     prompt_template: str = SYSTEM_PROMPT) -> Tuple[RespostaEmStream, str, str]:
    """
    Como o query_rag, mas a resposta chega em streaming.
    Retorna (stream, fontes, consulta usada na busca); as métricas ficam no próprio stream
    depois que ele termina (use formatar_metricas).
    """
    messages, fontes, consulta = _preparar_consulta(question, chat_history, prompt_template)
    return chat_llm_stream(messages, temperature=TEMPERATURE_ASSISTANT), fontes, consulta