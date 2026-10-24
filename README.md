# 🎲 RPG Tabletop AI Assistant (D&D 5e - Edições 2024/2025)

> Um assistente de IA inteligente, modular e 100% privado (*offline-first*) desenvolvido para apoiar Mestres (DMs) e Jogadores em sessões de *Dungeons & Dragons 5e*.

---

## 🎯 Para que serve este projeto?
Jogar RPG de mesa exige consultar dezenas de manuais, gerir combates complexos e interpretar regras rapidamente. Este assistente resolve isso ao dividir-se em **três módulos especializados** acessíveis numa interface gráfica simples:

1. 🧙‍♂️ **Módulo 1: Tutor, Regras e Lore (RAG)**
   - **O que faz:** Responde a qualquer dúvida sobre regras oficiais (Edições Core 2024/2025), explica condições, magias e contextualiza a história de mundos e facções.
   - **Diferencial:** Traduz os termos mecânicos mantendo a referência original em inglês (ex: *Condição Agarrado [Grappled]*) e indica as fontes exatas dos manuais. Também cria NPCs, encontros e itens mágicos sob demanda.

2. 🗺️ **Módulo 2: Simulador Mestre (Dungeon Master)**
   - **O que faz:** Assume o papel de Mestre de Jogo numa aventura solo (*One-on-One*). 
   - **Diferencial:** Constrói ambientes imersivos, controla monstros segundo as regras oficiais, exige testes de atributos com Classes de Dificuldade (CD) adequadas e **nunca** toma decisões pelo jogador.

3. ⚔️ **Módulo 3: Simulador Jogador (AI PC)**
   - **O que faz:** Atua como um colega de mesa genuíno (Personagem Controlado por IA).
   - **Diferencial:** Responde de forma imersiva (*in-character*) aos cenários propostos, interpretando a personalidade, a classe e o alinhamento definidos na ficha do personagem.

---

## ⚙️ Como funciona por trás dos panos?
A aplicação foi construída com foco em **privacidade e autonomia**, rodando inteiramente na tua máquina sem depender de APIs pagas ou internet:
* **LLM Local (Ollama / Llama 3):** Processa todas as respostas e diálogos de forma local. O próprio sistema verifica e inicia o servidor do Ollama automaticamente ao arrancar.
* **RAG (Retrieval-Augmented Generation):** Utiliza busca semântica vetorial (**ChromaDB**) sobre os manuais em PDF/Markdown armazenados localmente, garantindo que a IA baseie as respostas nas regras oficiais e não em alucinações.
* **Interface Gráfica (Streamlit):** Oferece um painel web moderno com histórico de conversas isolado por módulo.

---

## 🛠️ Stack Tecnológica
* **Linguagem:** Python 3.10+
* **Interface:** Streamlit
* **IA & RAG:** LangChain & ChromaDB
* **Modelo Local:** Ollama (`llama3`)
* **Embeddings:** HuggingFace (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`)

---

## 🚀 Como Executar na Própria Máquina

Siga os passos abaixo para configurar e rodar o projeto no seu computador:

### 1. Pré-requisitos
Certifique-se de ter instalado:
* **Python** (versão 3.10 ou superior)
* **Ollama** ([Descarregar em ollama.com](https://ollama.com))

Com o Ollama instalado, descarregue o modelo Llama 3 executando no seu terminal:

    ollama pull llama3
2. Clonar o Repositório e Instalar Dependências

Abra o terminal na pasta onde deseja guardar o projeto:
Bash

git clone [https://github.com/FredsonArthur/rpg-ai-assistant.git](https://github.com/FredsonArthur/rpg-ai-assistant.git)
cd rpg-ai-assistant

# Criar e ativar o ambiente virtual
    python -m venv venv
    source venv/bin/activate 
    No Windows: venv\Scripts\activate

# Instalar as bibliotecas necessárias
    pip install -r requirements.txt

3. Adicionar os Manuais de Regras

Para que o motor de busca (RAG) funcione, coloque os seus ficheiros de regras (.pdf ou .md) dentro da respetiva estrutura de pastas na raiz do projeto:

    data/
    └── rulebooks/
        ├── core/        # Ex: Livro do Jogador, Manual dos Monstros
        └── suplements/  # Ex: Suplementos e guias de cenários

4. Indexar a Base de Dados Vetorial

Execute o comando abaixo para processar os manuais e gerar os embeddings locais:

    python -c "from src.rag_engine import build_vector_store; build_vector_store()"

5. Iniciar a Aplicação

Agora basta iniciar o painel interativo. O sistema tentará ligar-se ao Ollama automaticamente:

    streamlit run app.py

O navegador abrirá automaticamente na página da aplicação (geralmente em http://localhost:8501). Utilize o menu lateral para alternar entre os módulos!

# 👥 Autoria

Desenvolvido por Fredson Arthur da Silva Gomes

Projeto de âmbito acadêmico e de investigação focado em Engenharia de Software, Sistemas Operacionais e Aplicações Práticas de Inteligência Artificial Local.