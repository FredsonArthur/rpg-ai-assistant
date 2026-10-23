# 🎲 RPG Tabletop AI Assistant (D&D 5e - Edições 2024/2025)

> **Projeto Acadêmico / Estudo de Engenharia de Software e IA**  
> Um assistente inteligente e unificado para RPGs de mesa, construído com arquitetura *offline-first*, RAG (Retrieval-Augmented Generation) e modelos locais de IA.

---

## 📌 Sobre o Projeto

Este projeto foi desenvolvido no contexto acadêmico com o objetivo de projetar e implementar um assistente de IA robusto voltado para Jogadores e Mestres (Dungeon Masters) de *Dungeons & Dragons 5e*. 

A aplicação prioriza a **privacidade, modularidade e independência de conexão**, operando inteiramente de forma local (*offline-first*) através do Ollama (Llama 3) e busca vetorial semântica (ChromaDB), garantindo respostas precisas e em Português do Brasil baseadas nos manuais oficiais de regras e suplementos.

---

## 🏗️ Arquitetura Unificada

O sistema utiliza uma **interface de chat unificada** capaz de identificar e responder de forma fluida a três grandes pilares de suporte ao jogo:

1. 🧙‍♂️ **Tutor de Regras:** Explica mecânicas, testes de resistência, condições e magias com termos oficiais em português seguidos do original em inglês (`[English Terms]`).
2. 📖 **Arquivista de Lore:** Consulta detalhes de cenários, monstros, deuses, facções e panteões do multiverso de D&D.
3. ⚔️ **Mestre Copiloto (Geração de Conteúdo):** Cria encontros, fichas simplificadas de NPCs, itens mágicos e ganchos de aventura formatados para leitura rápida em mesa.

---

## 🛠️ Stack Tecnológica

* **Linguagem:** Python 3.10+
* **Interface Gráfica:** Streamlit
* **Orquestração de IA & RAG:** LangChain
* **Banco de Dados Vetorial:** ChromaDB
* **Modelo LLM Local:** Ollama (`llama3`)
* **Embeddings Multilíngues:** HuggingFace (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`)
* **Processamento:** Otimizado para execução local em CPU/GPU

---

## 📁 Estrutura do Repositório

```
rpg-ai-assistant/
├── data/
│   ├── rulebooks/       # Acervo de manuais organizados em subpastas (.md / .pdf)
│   │   ├── core/        # Livros básicos (Player's Handbook, Monster Manual, DMG)
│   │   └── suplements/  # Suplementos (Tasha's, Xanathar's, Fizban's, etc.)
│   └── vectordb/        # Banco de dados vetorial persistido (ChromaDB - ignorado no Git)
├── src/
│   ├── config.py        # Configurações globais (Chunking, Top-K, Modelos, Diretórios)
│   ├── rag_engine.py    # Pipeline de busca recursiva, embeddings e integração com Ollama
│   └── prompt_templates.py # Central com o SYSTEM_PROMPT unificado do assistente
├── app.py               # Interface de chat moderna construída em Streamlit
├── requirements.txt     # Dependências do projeto
└── README.md            # Documentação oficial do repositório
```
## 🚀 Como Executar o Projeto Localmente

1. Pré-requisitos

    Python 3.10+ instalado.

Ollama baixado e instalado (ollama.com).
Modelo Llama 3 baixado no Ollama:

    ollama pull llama3

2. Clonar o repositório e configurar o ambiente

    git clone [https://github.com/FredsonArthur/rpg-ai-assistant.git](https://github.com/FredsonArthur/rpg-ai-assistant.git)
    cd rpg-ai-assistant

# Criar e ativar o ambiente virtual
    python -m venv venv
    source venv/bin/activate  # No Windows: venv\Scripts\activate

# Instalar as dependências
    pip install -r requirements.txt

3. Organizar os Manuais de Regras

Coloque seus arquivos .pdf ou .md organizados dentro do diretório data/rulebooks/ (ex: data/rulebooks/core/ e data/rulebooks/suplements/).

4. Indexar o Banco Vetorial

Execute o script para processar os manuais de forma recursiva e criar o banco vetorial local:

    python -c "from src.rag_engine import build_vector_store; build_vector_store()"

5. Iniciar a Aplicação

certifique-se de que o serviço do Ollama está rodando em um terminal:
    ollama serve

Em outro terminal (com o ambiente virtual ativo), inicie o Streamlit:

    streamlit run app.py

## 👥 Autoria

    Desenvolvido por Fredson Arthur da Silva Gomes como parte de projeto de estudo e pesquisa acadêmica em Inteligência Artificial e Sistemas Operacionais/Engenharia de Software.