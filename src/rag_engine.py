"""
Módulo de Mecanismo de RAG (Retrieval-Augmented Generation)
------------------------------------------------------------
Este script gerencia todo o pipeline de RAG para o assistente de RPG:
1. Carregamento dos livros e documentos de regras/lore (PDFs e Markdown).
2. Divisão inteligente do texto em fragmentos (Chunking).
3. Geração de vetores através de Embeddings (HuggingFace).
4. Persistência e busca semântica em Banco Vetorial local (ChromaDB).
5. Construção de Prompts estruturados para os Casos de Uso UC01, UC02 e UC03.

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

# Configurações globais ou caminhos padrão caso o arquivo src/config.py não esteja isolado
RULEBOOKS_DIR = "data/rulebooks"
VECTORDB_DIR = "data/vectordb"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
TOP_K_RESULTS = 4
OLLAMA_MODEL = "llama3"  # Ou outro modelo configurado no seu Ollama local


def get_embeddings() -> HuggingFaceEmbeddings:
    """
    Inicializa e retorna o modelo de Embeddings do HuggingFace.
    Utiliza CPU ou GPU dependendo da disponibilidade do ambiente.
    """
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={'device': 'cpu'},  # Altere para 'cuda' se possuir placa NVIDIA configurada
        encode_kwargs={'normalize_embeddings': True}
    )


def build_vector_store() -> Optional[Chroma]:
    """
    Processa os livros (PDF e Markdown) da pasta de dados e cria a base vetorial.
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
        print(f"ℹ️ Nenhum PDF carregado ou erro menor: {e}")
        
    try:
        documents.extend(md_loader.load())
    except Exception as e:
        print(f"ℹ️ Nenhum Markdown carregado ou erro menor: {e}")

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

    print("💾 [RAG Engine] Gerando embeddings e persistindo no ChromaDB...")
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
    Busca por similaridade semântica os trechos mais relevantes e extrai as fontes.
    """
    db = load_vector_store()
    if not db:
        return "⚠️ Banco vetorial não inicializado.", "Nenhuma fonte"

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
    Executa o pipeline completo de RAG de acordo com o caso de uso escolhido:
    - 'regras' -> UC01: Consultar Regras ou Mecânicas
    - 'lore'   -> UC02: Consultar Lore e Ambientação
    - 'criacao'-> UC03: Gerar Conteúdo Auxiliar para Mestre
    """
    # 1. Recupera o contexto do Banco Vetorial
    contexto, fontes = recuperar_contexto(query, k=TOP_K_RESULTS)

    # 2. Define o System Prompt específico com base no Caso de Uso
    if tipo == "regras":
        system_prompt = f"""Você é um tutor especialista nas regras oficiais do sistema de RPG consultado.
Responda à pergunta do usuário utilizando estritamente os trechos de livros fornecidos abaixo no bloco <contexto>.
Regras:
- Se a informação não estiver no contexto fornecido, diga claramente: "Não encontrei essa informação nos livros cadastrados."
- Seja direto e objetivo na explicação da regra.
- Sempre cite no final de qual livro ou trecho a regra foi retirada.

<contexto>
{contexto}
</contexto>"""

    elif tipo == "lore":
        system_prompt = f"""Você é um historiador e arquivista lendário especialista no universo e na história (lore) do cenário de RPG.
Responda à pergunta do usuário sobre a história, geografia ou lendas do mundo utilizando exclusivamente os fatos presentes no bloco <lore_contexto>.
Regras:
- Adote um tom respeitoso, imersivo e informativo (de um sábio/arquivista).
- Se a informação não estiver presente no contexto, diga: "Não há registros sobre este assunto nos tomos e livros carregados."

<lore_contexto>
{contexto}
</lore_contexto>"""

    elif tipo == "criacao":
        system_prompt = f"""Você é um co-criador e assistente criativo de Mestres de RPG, especialista em criar conteúdos originais balanceados e imersivos.
Crie o conteúdo solicitado pelo usuário utilizando as regras de balanceamento e mecânicas presentes no bloco <regras_referencia>.
Regras:
- O conteúdo gerado deve respeitar o nível de poder (CR ou Nível) indicado pelo usuário.
- Formate a saída de forma limpa, dividindo entre História/Personalidade e Estatísticas/Mecânicas.

<regras_referencia>
{contexto}
</regras_referencia>"""

    else:
        system_prompt = f"Responda à pergunta com base no contexto:\n{contexto}"

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
        
        # Simula ou extrai métricas básicas se disponíveis
        prompt_tokens = response.get('prompt_eval_count', 0)
        completion_tokens = response.get('eval_count', 0)
        metricas = f"Prompt Tokens: {prompt_tokens} | Completion Tokens: {completion_tokens}"
        
        return resposta_llm, fontes, metricas

    except Exception as e:
        return f"Erro ao comunicar com o Ollama local: {e}. Verifique se o serviço do Ollama está rodando.", "N/A", "N/A"