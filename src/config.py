"""
Módulo de Configurações Globais
-------------------------------
Centraliza os caminhos de diretórios, parâmetros do RAG e configurações do modelo.
Os valores de modelo podem ser trocados sem editar o código, por variável de ambiente
(ex.: OLLAMA_MODEL=llama3.1 streamlit run app.py).
"""

import os

# ==========================================
# Caminhos de Diretórios
# ==========================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULEBOOKS_DIR = os.path.join(BASE_DIR, "data", "rulebooks")
VECTORDB_DIR = os.path.join(BASE_DIR, "data", "vectordb")

# ==========================================
# Parâmetros do RAG
# ==========================================
# ATENÇÃO: alterar EMBEDDING_MODEL_NAME, CHUNK_SIZE ou CHUNK_OVERLAP deixa a base vetorial
# antiga incompatível. Depois de mudar qualquer um deles, rode a indexação de novo
# (build_vector_store), que recria data/vectordb do zero.
# Valores iniciais, ainda não validados com testes de recuperação.
CHUNK_SIZE = 1500          # Tamanho do trecho, em caracteres
CHUNK_OVERLAP = 300        # Sobreposição entre trechos vizinhos, em caracteres
EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Quantidade de trechos recuperados por modo de uso
TOP_K_RESULTS = 8          # Assistente (dúvidas de regras, lore e criação de conteúdo)
TOP_K_MASTER = 3           # IA como Mestre
TOP_K_PLAYER = 2           # IA como Jogador

# Quantidade de mensagens recentes enviadas ao modelo (Mestre e Jogador)
HISTORY_WINDOW = 10

# ==========================================
# Modelo Local (Ollama)
# ==========================================
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
# Janela de contexto enviada ao Ollama. O padrão do Ollama é baixo (2048-4096 tokens) e,
# quando o prompt estoura, o início (o system prompt) é cortado. Llama 3 suporta até 8192.
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))

# ==========================================
# Temperatura por modo (valores iniciais, a ajustar nos testes)
# ==========================================
TEMPERATURE_ASSISTANT = 0.3   # Regras: precisão e pouca invenção
TEMPERATURE_MASTER = 0.7      # Narrativa: mais criatividade

# Arquétipos do Jogador IA (UC07)
ARCHETYPE_TEMPERATURES = {
    "Iniciante": 0.5,   # previsível, focado em tirar dúvidas
    "Tático": 0.3,      # preciso e objetivo
    "Roleplay": 0.8,    # criativo, rico em falas
    "Personalizado": 0.6,  # perfil escrito pelo usuário
}
TEMPERATURE_FEEDBACK = 0.4    # Feedback pedagógico (UC09): analítico, com pouca invenção

# Garante que as pastas essenciais existam na raiz
os.makedirs(RULEBOOKS_DIR, exist_ok=True)
os.makedirs(VECTORDB_DIR, exist_ok=True)