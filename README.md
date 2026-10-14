# 🎲 RPG Tabletop AI Assistant

> **Projeto Acadêmico / Estudo de Engenharia de Software e IA**  
> Um assistente inteligente modular para RPGs de mesa, construído com arquitetura offline-first, RAG (Retrieval-Augmented Generation) e agentes locais.

---

## 📌 Sobre o Projeto

Este projeto foi desenvolvido no contexto acadêmico com o objetivo de projetar e implementar um assistente de IA robusto voltado para Jogadores e Mestres (Dungeon Masters) de RPGs de mesa (como *Dungeons & Dragons*). 

A aplicação prioriza a **privacidade, modularidade e independência de conexão**, operando inteiramente de forma local (offline-first) através de busca vetorial semântica e modelos locais, garantindo respostas precisas baseadas exclusivamente nos manuais oficiais de regras.

---

## 🏗️ Arquitetura e Módulos

O sistema é dividido em **3 módulos principais** (cobrindo 9 Casos de Uso - UC01 a UC09):

1. 🧙‍♂️ **Módulo Tutor (Regras & Regras do Sistema):** Explica mecânicas, testes de resistência, magias e condições baseando-se diretamente nos livros oficiais indexados.
2. 🗺️ **Módulo Dungeon Master / Mestre (DM):** Auxilia na criação de campanhas, narração de combates, geração de NPCs e gerenciamento de lore customizada.
3. ⚔️ **Módulo Player (Jogador):** Ajuda na criação de fichas, progressão de personagem, escolha de magias e otimização tática.

---

## 🛠️ Stack Tecnológica

* **Linguagem:** Python
* **Interface Gráfica:** Streamlit
* **Orquestração de IA & RAG:** LangChain
* **Banco de Dados Vetorial:** ChromaDB
* **Embeddings:** HuggingFace (`sentence-transformers/all-MiniLM-L6-v2`)
* **Processamento:** Otimizado para execução local (Suporte a CPU/GPU via PyTorch)

---

## 📁 Estrutura do Repositório

```text
rpg-ai-assistant/
├── data/
│   ├── rulebooks/       # Manuais e compêndios de regras em formato .md ou .pdf
│   └── vectordb/        # Banco de dados vetorial persistido (ChromaDB)
├── src/
│   ├── config.py        # Configurações globais e variáveis de ambiente
│   ├── rag_engine.py    # Pipeline de indexação, chunking e busca semântica
│   └── prompt_templates.py # Central de prompts para os módulos (Tutor, DM, Player)
├── requirements.txt     # Dependências do projeto
└── README.md            # Documentação do projeto
```
## 🚀 Como Executar o Projeto Localmente
### 1. Pré-requisitos

    Python 3.10 ou superior instalado.

    Git.

### 2. Clonar o repositório e configurar o ambiente

git clone [https://github.com/FredsonArthur/rpg-ai-assistant.git](https://github.com/FredsonArthur/rpg-ai-assistant.git)
cd rpg-ai-assistant

# (Opcional) Crie e ative um ambiente virtual
    python -m venv venv
    source venv/bin/activate  # No Windows: venv\Scripts\activate

# Instale as dependências
    pip install -r requirements.txt

### 3. Adicionar Manuais de Regras

Coloque os arquivos de regras (em formato Markdown .md ou PDF .pdf) dentro da pasta:

    data/rulebooks/

### 4. Executar a Indexação e Teste do RAG Engine

Para popular o banco vetorial e testar a busca semântica:

    PYTHONPATH=. python src/rag_engine.py

## 👥 Autoria

    Desenvolvido por Fredson Arthur da Silva Gomes como parte de projeto de estudo e pesquisa acadêmica.