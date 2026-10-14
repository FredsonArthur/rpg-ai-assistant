"""
Módulo de Mecanismo de RAG (Retrieval-Augmented Generation)
------------------------------------------------------------
Este script é responsável pelo pipeline completo de RAG:
1. Carregamento dos documentos (PDFs de regras/lore).
2. Divisão do texto em fragmentos (Chunking).
3. Vetorização do texto via modelo de Embeddings.
4. Persistência e busca por similaridade semântica no Banco Vetorial (ChromaDB).

Autor: Projeto RPG AI Assistant
Data: 2026
"""

import os
from typing import List, Optional

# Importações da comunidade e do ecossistema LangChain
from langchain_community.document_loaders import PyPDFLoader, TextLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

# Importação das configurações globais do projeto
from src.config import (
    RULEBOOKS_DIR,
    VECTORDB_DIR,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    EMBEDDING_MODEL_NAME,
    TOP_K_RESULTS
)


def get_embeddings() -> HuggingFaceEmbeddings:
    """
    Inicializa e retorna o modelo de Embeddings do HuggingFace configurado para rodar na GPU (CUDA).
    """
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={'device': 'cuda'},  # Força o uso da GPU para processamento mais rápido
        encode_kwargs={'normalize_embeddings': True}
    )
    )


def build_vector_store() -> Optional[Chroma]:
    """
    Processa os livros (PDF ou Markdown) da pasta de dados e cria a base vetorial.
    """
    print(f"📄 [RAG Engine] Lendo livros (PDF/MD) no diretório: {RULEBOOKS_DIR}...")
    
    # Carrega arquivos .pdf
    pdf_loader = DirectoryLoader(RULEBOOKS_DIR, glob="./*.pdf", loader_cls=PyPDFLoader)
    # Carrega arquivos .md (Markdown)
    md_loader = DirectoryLoader(RULEBOOKS_DIR, glob="./*.md", loader_cls=TextLoader)
    
    documents: List[Document] = pdf_loader.load() + md_loader.load()

    if not documents:
        print("⚠️ [RAG Engine] Nenhum arquivo PDF ou Markdown encontrado na pasta data/rulebooks/.")
        return None

    print(f"✂️ [RAG Engine] Dividindo {len(documents)} documento(s) em chunks de texto...")
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""]
    )
    
    chunks: List[Document] = text_splitter.split_documents(documents)
    print(f"🧩 [RAG Engine] Total de chunks gerados para indexação: {len(chunks)}")

    print("💾 [RAG Engine] Gerando vetores (Embeddings) e salvando no ChromaDB local...")
    embeddings = get_embeddings()
    
    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=VECTORDB_DIR
    )
    
    print("✅ [RAG Engine] Banco Vetorial construído e armazenado com sucesso!")
    return vector_store


def load_vector_store() -> Optional[Chroma]:
    """
    Carrega a base vetorial já existente e persistida no disco.

    Garante reuso rápido sem precisar processar novamente os PDFs toda vez
    que o sistema for iniciado.

    Returns:
        Optional[Chroma]: Instância do banco vetorial carregada ou None se não existir.
    """
    embeddings = get_embeddings()
    
    # Verifica se a pasta existe e não está vazia
    if os.path.exists(VECTORDB_DIR) and os.listdir(VECTORDB_DIR):
        return Chroma(
            persist_directory=VECTORDB_DIR,
            embedding_function=embeddings
        )
    
    return None


def search_rules(query: str, k: int = TOP_K_RESULTS) -> str:
    """
    Realiza a busca por similaridade semântica no banco vetorial.

    Dada uma consulta em linguagem natural do usuário (ex: 'Como funciona o descanso longo?'),
    esta função encontra os 'k' fragmentos de texto mais próximos/relevantes no espaço vetorial.

    Args:
        query (str): Pergunta ou termos de busca fornecidos pelo usuário.
        k (int, optional): Número de fragmentos mais relevantes a retornar. Padrão: TOP_K_RESULTS.

    Returns:
        str: Bloco de texto formatado contendo os trechos resgatados e suas respectivas fontes/páginas,
             pronto para ser injetado no System Prompt da LLM.
    """
    db = load_vector_store()
    
    # Caso a base ainda não tenha sido criada pelo usuário
    if not db:
        return "⚠️ O Banco Vetorial ainda não foi inicializado ou está vazio. Execute a criação da base primeiro."

    # Executa a busca por proximidade vetorial (Similarity Search)
    results: List[Document] = db.similarity_search(query, k=k)
    
    if not results:
        return "Nenhum trecho de regra relevante foi encontrado para esta consulta."

    # Formata cada fragmento com seus metadados (nome do arquivo e número da página)
    context_chunks = []
    for doc in results:
        source_file = os.path.basename(doc.metadata.get('source', 'Livro Desconhecido'))
        page = doc.metadata.get('page', 0) + 1  # O PyPDF converte página 1 para índice 0, então ajustamos (+1)
        
        chunk_text = (
            f"📖 [Fonte: {source_file} - Pág. {page}]\n"
            f"{doc.page_content.strip()}"
        )
        context_chunks.append(chunk_text)

    # Junta todos os chunks recuperados com um separador legível
    return "\n\n---\n\n".join(context_chunks)


if __name__ == "__main__":
    """
    Bloco de teste direto do arquivo.
    Permite rodar 'python src/rag_engine.py' no terminal para criar/testar o banco vetorial.
    """
    print("🚀 === Iniciando Teste de Execução do RAG Engine ===")
    
    # 1. Tenta construir ou atualizar o banco vetorial a partir dos PDFs
    build_vector_store()
    
    # 2. Teste rápido de busca semântica
    pergunta_teste = "Como funciona o teste de resistência?"
    print(f"\n🔍 Testando busca para a pergunta: '{pergunta_teste}'\n")
    
    resultado_busca = search_rules(pergunta_teste, k=2)
    print("--- Resultado do Contexto Recuperado ---")
    print(resultado_busca)
    print("---------------------------------------")