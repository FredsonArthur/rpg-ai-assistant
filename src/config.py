import os

# Caminhos de Diretórios
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULEBOOKS_DIR = os.path.join(BASE_DIR, "data", "rulebooks")
VECTORDB_DIR = os.path.join(BASE_DIR, "data", "vectordb")

# Parâmetros de Processamento do RAG
CHUNK_SIZE = 600          # Tamanho de cada pedaço de texto em caracteres
CHUNK_OVERLAP = 100       # Sobreposição entre chunks para não perder contexto
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K_RESULTS = 3         # Quantidade de trechos retornados por busca

# Garante que as pastas existam
os.makedirs(RULEBOOKS_DIR, exist_ok=True)
os.makedirs(VECTORDB_DIR, exist_ok=True)