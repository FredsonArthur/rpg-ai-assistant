"""
Módulo de Mecanismo de RAG (Retrieval-Augmented Generation)
------------------------------------------------------------
Este script gerencia todo o pipeline de RAG para o assistente de RPG:
1. Carregamento dos livros e documentos de regras/lore (PDFs e Markdown).
2. Divisão inteligente do texto em fragmentos (Chunking).
3. Geração de vetores através de Embeddings Multilíngues (HuggingFace).
4. Persistência e busca semântica em Banco Vetorial local (ChromaDB).
5. Orquestração das respostas via Ollama (Llama 3) utilizando os templates de prompt.

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

# Importação dos templates de prompts estruturados para cada Caso de Uso
from src.prompt_templates import PROMPT_UC01, PROMPT_UC02, PROMPT_UC03

# Configurações globais e diretórios do projeto
RULEBOOKS_DIR = "data/rulebooks"
VECTORDB_DIR = "data/vectordb"
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 300

# Alterado para modelo multilíngue para garantir compatibilidade entre termos em PT-BR e manuais em EN
EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

TOP_K_RESULTS = 8
OLLAMA_MODEL = "llama3"  # Modelo executado localmente via Ollama


def get_embeddings() -> HuggingFaceEmbeddings:
    """
    Inicializa e retorna o modelo de Embeddings Multilíngue do HuggingFace.
    Garante o alinhamento semântico entre consultas em português e manuais em inglês.
    """
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={'device': 'cpu'},  # Altere para 'cuda' se possuir suporte a GPU configurado
        encode_kwargs={'normalize_embeddings': True}
    )


def build_vector_store() -> Optional[Chroma]:
    """
    Processa os livros (PDF e Markdown) da pasta de dados, aplica o chunking,
    gera os embeddings multilíngues e persiste a base vetorial no ChromaDB.
    """
    print(f"📄 [RAG Engine] Lendo documentos em: {RULEBOOKS_DIR}...")
    
    if not os.path.exists(RULEBOOKS_DIR):
        os.makedirs(RULEBOOKS_DIR, exist_ok=True)
        print(f"⚠️ Diretório {RULEBOOKS_DIR} criado. Adicione os livros em PDF ou Markdown nele.")
        return None

    pdf_loader = DirectoryLoader(RULEBOOKS_DIR, glob="./*.pdf", loader_cls=PyPDFLoader)
    md_loader = DirectoryLoader(RULEBOOKS_DIR, glob="./*.md", loader_cls=TextLoader)
    
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
        print("⚠️ [RAG Engine] Nenhum arquivo PDF ou Markdown encontrado na pasta de regras.")
        return None

    print(f"✂️ [RAG Engine] Dividindo {len(documents)} documento(s) em chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""]
    )
    
    chunks: List[Document] = text_splitter.split_documents(documents)
    print(f"🧩 [RAG Engine] Total de chunks gerados: {len(chunks)}")

    print("💾 [RAG Engine] Gerando embeddings multilíngues e persistindo no ChromaDB...")
    embeddings = get_embeddings()
    
    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=VECTORDB_DIR
    )
    
    print("✅ [RAG Engine] Banco Vetorial construído com sucesso!")
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
        return "⚠️ Banco vetorial não inicializado. Execute a indexação dos manuais.", "Nenhuma fonte"

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


def consultar_rag(query: str, tipo: str = "regras") -> Tuple[str, str, str]:
    """
    Executa o pipeline completo de RAG direcionando para o template de prompt adequado:
    - 'regras'  -> UC01: Consultar Regra ou Mecânica (Tutor)
    - 'lore'    -> UC02: Consultar Lore e Ambientação (Arquivista)
    - 'criacao' -> UC03: Gerar Conteúdo Auxiliar para Mestre (DM Copiloto)
    """
    # 1. Recupera o contexto do Banco Vetorial com base na consulta
    contexto, fontes = recuperar_contexto(query, k=TOP_K_RESULTS)

    # 2. Seleciona o System Prompt correspondente ao Caso de Uso
    if tipo == "regras":
        system_prompt = PROMPT_UC01.format(context=contexto, question=query)
    elif tipo == "lore":
        system_prompt = PROMPT_UC02.format(context=contexto, question=query)
    elif tipo == "criacao":
        system_prompt = PROMPT_UC03.format(context=contexto, question=query)
    else:
        # Fallback genérico caso o tipo não seja mapeado
        system_prompt = f"Responda à pergunta com base no contexto:\n{contexto}\n\nPergunta: {query}"

    # 3. Executa a chamada à LLM local via Ollama
    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ]
        )
        resposta_llm = response['message']['content']
        
        # Extração de métricas de uso de tokens da resposta do Ollama
        prompt_tokens = response.get('prompt_eval_count', 0)
        completion_tokens = response.get('eval_count', 0)
        metricas = f"Prompt Tokens: {prompt_tokens} | Completion Tokens: {completion_tokens}"
        
        return resposta_llm, fontes, metricas

    except Exception as e:
        error_msg = f"Erro ao comunicar com o Ollama local: {e}. Verifique se o serviço do Ollama está rodando ('ollama serve')."
        return error_msg, "N/A", "N/A"