"""
Módulo de Configurações Globais
-------------------------------
Centraliza os caminhos de diretórios, parâmetros de processamento do RAG
e configurações de modelos do projeto.
"""

import os

# Caminhos de Diretórios
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULEBOOKS_DIR = os.path.join(BASE_DIR, "data", "rulebooks")
VECTORDB_DIR = os.path.join(BASE_DIR, "data", "vectordb")

# Parâmetros de Processamento do RAG (Validados para D&D 5e)
CHUNK_SIZE = 1500          # Tamanho ideal em caracteres para capturar regras/descrições completas
CHUNK_OVERLAP = 300       # Sobreposição para garantir continuidade de contexto entre chunks
EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
TOP_K_RESULTS = 8         # Quantidade de trechos recuperados para abranger os novos suplementos

# Configuração do Modelo Local (Ollama)
OLLAMA_MODEL = "llama3"

# Garante que as pastas essenciais existam na raiz
os.makedirs(RULEBOOKS_DIR, exist_ok=True)
os.makedirs(VECTORDB_DIR, exist_ok=True)