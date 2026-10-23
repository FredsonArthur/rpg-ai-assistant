"""
Módulo de Mecanismo de RAG (Retrieval-Augmented Generation)
------------------------------------------------------------
Este script gere todo o pipeline de RAG unificado para o assistente de RPG:
1. Carregamento dos livros e documentos de regras/lore (PDFs e Markdown) com suporte recursivo a subpastas.
2. Divisão inteligente do texto em fragmentos (Chunking).
3. Geração de vetores através de Embeddings Multilíngues (HuggingFace).
4. Persistência e busca semântica em Base Vetorial local (ChromaDB).
5. Orquestração das respostas via Ollama (Llama 3) utilizando o prompt unificado.

Autor: Projeto RPG AI Assistant
Data: 2026
"""

import os
from typing import List, Optional, Tuple

from langchain_community.document_loaders import PyPDFLoader, TextLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
import ollama

# Importação do prompt unificado do sistema e das configurações centrais
from src.prompt_templates import SYSTEM_PROMPT
from src.config import (
    RULEBOOKS_DIR,
    VECTORDB_DIR,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    EMBEDDING_MODEL_NAME,
    TOP_K_RESULTS,
    OLLAMA_MODEL
)


def get_embeddings() -> HuggingFaceEmbeddings:
    """
    Inicializa e retorna o modelo de Embeddings Multilíngue do HuggingFace.
    """
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )


def build_vector_store() -> Optional[Chroma]:
    """
    Processa os livros (PDF e Markdown) da pasta de dados e subpastas de forma recursiva,
    aplica o chunking, gera os embeddings multilíngues e persiste a base vetorial no ChromaDB.
    """
    print(f"📄 [RAG Engine] A ler documentos recursivamente em: {RULEBOOKS_DIR}...")
    
    if not os.path.exists(RULEBOOKS_DIR):
        os.makedirs(RULEBOOKS_DIR, exist_ok=True)
        print(f"⚠️ Diretório {RULEBOOKS_DIR} criado. Adicione os livros em PDF ou Markdown nele.")
        return None

    # Carregadores configurados com busca recursiva para abranger core/ e suplements/
    pdf_loader = DirectoryLoader(
        RULEBOOKS_DIR, 
        glob="**/*.pdf", 
        loader_cls=PyPDFLoader, 
        recursive=True
    )
    md_loader = DirectoryLoader(
        RULEBOOKS_DIR, 
        glob="**/*.md", 
        loader_cls=TextLoader, 
        recursive=True
    )
    
    documents: List[Document] = []
    try:
        documents.extend(pdf_loader.load())
    except Exception as e:
        print(f"ℹ️ Nenhum PDF carregado ou aviso: {e}")
        
    try:
        documents.extend(md_loader.load())
    except Exception as e:
        print(f"ℹ️ Nenhum Markdown carregado ou aviso: {e}")

    if not documents:
        print("⚠️ [RAG Engine] Nenhum ficheiro PDF ou Markdown encontrado na pasta de regras.")
        return None

    print(f"✂️ [RAG Engine] A dividir {len(documents)} documento(s) em chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""]
    )
    
    chunks: List[Document] = text_splitter.split_documents(documents)
    print(f"🧩 [RAG Engine] Total de chunks gerados: {len(chunks)}")

    print("💾 [RAG Engine] A gerar embeddings multilíngues e a persistir no ChromaDB...")
    embeddings = get_embeddings()
    
    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=VECTORDB_DIR
    )
    
    print("✅ [RAG Engine] Base Vetorial construída com sucesso!")
    return vector_store


def load_vector_store() -> Optional[Chroma]:
    """
    Carrega a base vetorial já existente e persistida no disco.
    """
    embeddings = get_embeddings()
    if os.path.exists(VECTORDB_DIR) and os.listdir(VECTORDB_DIR):
        return Chroma(
            persist_directory=VECTORDB_DIR,
            embedding_function=embeddings
        )
    return None


def recuperar_contexto(query: str, k: int = TOP_K_RESULTS) -> Tuple[str, str]:
    """
    Realiza a busca por similaridade semântica (multilíngue) retornando
    os trechos mais relevantes e as fontes bibliográficas correspondentes.
    """
    db = load_vector_store()
    if not db:
        return "⚠️ Base vetorial não inicializada. Execute a indexação dos manuais.", "Nenhuma fonte"

    results: List[Document] = db.similarity_search(query, k=k)
    if not results:
        return "Nenhum trecho relevante encontrado.", "Desconhecido"

    context_chunks = []
    fontes_encontradas = set()

    for doc in results:
        source_file = os.path.basename(doc.metadata.get('source', 'Livro Oficial'))
        page = doc.metadata.get('page', 0)
        page_str = f" - Pág. {page + 1}" if page else ""
        
        fontes_encontradas.add(f"{source_file}{page_str}")
        
        chunk_text = f"📖 [Fonte: {source_file}{page_str}]\n{doc.page_content.strip()}"
        context_chunks.append(chunk_text)

    texto_contexto = "\n\n---\n\n".join(context_chunks)
    str_fontes = ", ".join(fontes_encontradas)
    
    return texto_contexto, str_fontes


def query_rag(question: str, prompt_template: str = SYSTEM_PROMPT) -> Tuple[str, str, str]:
    """
    Função principal unificada de consulta RAG para o chat.
    Recupera o contexto, formata o prompt unificado e executa a chamada ao Ollama.
    """
    # 1. Recupera o contexto dos manuais
    contexto, fontes = recuperar_contexto(question, k=TOP_K_RESULTS)

    # 2. Formata o prompt unificado com o contexto e a pergunta
    system_prompt = prompt_template.format(context=contexto, question=question)

    # 3. Executa a chamada à LLM local via Ollama
    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ]
        )
        resposta_llm = response['message']['content']
        
        # Extração de métricas de uso de tokens
        prompt_tokens = response.get('prompt_eval_count', 0)
        completion_tokens = response.get('eval_count', 0)
        metricas = f"Prompt Tokens: {prompt_tokens} | Completion Tokens: {completion_tokens}"
        
        return resposta_llm, fontes, metricas

    except Exception as e:
        error_msg = f"Erro ao comunicar com o Ollama local: {e}. Verifique se o serviço do Ollama está rodando ('ollama serve')."
        return error_msg, "N/A", "N/A"