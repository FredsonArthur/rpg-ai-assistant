# 🎲 RPG Tabletop AI Assistant (D&D 5e)

> Um assistente de IA que roda **100% no seu computador**, sem internet depois da instalação, para apoiar Mestres e Jogadores de *Dungeons & Dragons 5e* (edições 2024/2025). Ele tira dúvidas sobre qualquer assunto, e, quando você pede, **vira o Mestre** de uma aventura ou **um jogador** para você treinar.

Projeto da disciplina **Tópicos Especiais em Inteligência Artificial**: um LLM local aplicado a um problema real, usando tokenização, embeddings, Transformer, engenharia de prompt e RAG.

---

## ✨ O que ele faz

Há um chat único com três modos de uso. Você troca de modo pelo menu lateral, por comandos ou, no modo Assistente, escrevendo o pedido ("seja meu mestre").

| Modo | O que a IA faz | Como ativar |
|---|---|---|
| 🧙 **Assistente** (padrão) | Responde dúvidas sobre regras e lore de D&D com apoio dos livros (citando a fonte), cria NPCs, encontros e itens mágicos, e responde qualquer outra pergunta. | `/assistente` |
| 🗺️ **Mestre** | Conduz uma aventura solo: descreve a cena, pede testes com a CD adequada, controla monstros e combates. Você joga. | `/mestre` ou "seja meu mestre" |
| ⚔️ **Jogador** | Interpreta um personagem (perfil Iniciante, Tático, Roleplay ou Personalizado). Você é o Mestre e narra a cena. | `/jogador` ou "quero ser o mestre" |

**Comandos:** `/assistente`, `/mestre`, `/jogador`, `/feedback` (no modo Jogador, a IA analisa a sua condução como Mestre) e `/ajuda`.

Dentro de uma aventura ou sessão, só os comandos com `/` trocam de modo (ou "voltar ao assistente"). Assim, o que você narra ou faz no jogo nunca é confundido com um pedido de troca.

### Destaques

- **Respostas com fonte:** no modo Assistente, os trechos dos livros que embasaram a resposta aparecem com o livro de origem (marcado como *Core* ou *Suplemento*), junto com a contagem de tokens.
- **Memória de conversa:** perguntas como "e se eu estiver cego?" são reescritas com o contexto anterior antes da busca nos livros.
- **Combate confiável:** os dados dos monstros são sorteados em Python (a IA não "inventa" rolagens), e o estado do combate (PV e CA) é guardado e devolvido ao Mestre a cada turno.
- **Jogador sem metagame:** a IA jogadora não consulta os livros; ela só sabe o que você narrou.
- **Streaming:** as respostas do Assistente e do Mestre aparecem aos poucos.
- **Histórico separado por modo:** uma nova aventura começa do zero, e as sessões antigas ficam guardadas enquanto a página estiver aberta.

---

## 🧠 Conceitos de IA aplicados

| Conceito | Onde aparece no projeto |
|---|---|
| **Tokenização** | O modelo trabalha com tokens, e a janela de contexto é limitada (`OLLAMA_NUM_CTX`, em `src/config.py`). Cada resposta do Assistente exibe os tokens usados no prompt e na resposta. |
| **Embeddings** | Os trechos dos livros viram vetores com `paraphrase-multilingual-MiniLM-L12-v2`, guardados no ChromaDB. A pergunta também vira um vetor, e a busca traz os trechos mais próximos. |
| **Transformer** | O Llama 3 (via Ollama) e o modelo de embeddings são baseados em Transformers. O app controla a geração com a temperatura (por modo e por perfil de jogador) e a janela de contexto. |
| **Engenharia de prompt** | Todos os prompts ficam em `src/prompt_templates.py`: papéis, regras de conduta, contexto delimitado, formato de saída obrigatório, exemplo de resposta e reescrita da pergunta. |
| **RAG** | Livros → trechos → embeddings → busca por similaridade → contexto no prompt → resposta com fonte. |

---

## ⚙️ Como funciona

```
 Streamlit (app.py)  ──►  assistant.py  (comando, troca de modo, histórico de cada modo)
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
 module1_tutor.py     module2_master.py     module3_player.py
  (Assistente)            (Mestre)              (Jogador)
        │                     │                     │
        └──────► rag_engine.py (busca nos livros) ◄─┘   (o Jogador não usa)
                  │                 │
              ChromaDB          Ollama (Llama 3)
         (data/vectordb)      (chat_llm / chat_llm_stream)
```

## 🛠️ Stack

- **Linguagem:** Python 3.10+
- **Interface:** Streamlit
- **LLM local:** Ollama com `llama3`
- **RAG:** LangChain (leitores e divisão de texto) e ChromaDB
- **Embeddings:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`

## 📁 Estrutura do projeto

```
rpg-ai-assistant/
├── app.py                  # Interface (Streamlit): chat único e menu lateral
├── requirements.txt
├── data/
│   ├── rulebooks/          # Seus livros (.md ou .pdf)
│   │   ├── core/           # Livros Core (ex.: Livro do Jogador, Manual dos Monstros)
│   │   └── suplements/     # Suplementos e guias
│   └── vectordb/           # Base vetorial gerada (não vai para o GitHub)
└── src/
    ├── config.py           # Caminhos, parâmetros do RAG, modelo e temperaturas
    ├── prompt_templates.py # Todos os prompts do sistema
    ├── assistant.py        # Comandos, troca de modo e histórico por modo
    ├── rag_engine.py       # Indexação, busca, chamadas ao Ollama e streaming
    ├── ollama_service.py   # Verifica e inicia o servidor do Ollama
    ├── dice.py             # Dados sorteados em Python para o Mestre e o Jogador
    ├── utils.py            # Janela de histórico
    └── modules/
        ├── module1_tutor.py   # Modo Assistente
        ├── module2_master.py  # Modo Mestre
        └── module3_player.py  # Modo Jogador e feedback pós-sessão
```

---

## 🚀 Como executar

### 1. Pré-requisitos

- **Python 3.10 ou superior.** Se a instalação do PyTorch falhar em uma versão muito recente do Python, use o Python 3.12.
- **Ollama:** <https://ollama.com>
- Cerca de **8 GB de RAM** livres e uns 10 GB de disco (modelo, embeddings e dependências). Placa de vídeo não é necessária, mas deixa as respostas mais rápidas.

Instale o Ollama e baixe o modelo:

```bash
# Linux (no Windows e no macOS, baixe o instalador no site)
curl -fsSL https://ollama.com/install.sh | sh

ollama pull llama3
```

### 2. Baixar o projeto e instalar as dependências

Baixe o repositório (por exemplo, pelo GitHub Desktop em *File → Clone repository*, ou pelo terminal):

```bash
git clone https://github.com/FredsonArthur/rpg-ai-assistant.git
cd rpg-ai-assistant
```

Crie o ambiente virtual e instale as dependências:

```bash
python3 -m venv venv
source venv/bin/activate        # No Windows: venv\Scripts\activate

# PyTorch só para CPU (evita baixar vários GB de bibliotecas de GPU)
pip install torch --index-url https://download.pytorch.org/whl/cpu

pip install -r requirements.txt
```

### 3. Adicionar os livros de regras

Coloque os seus arquivos (`.md` ou `.pdf`) nas pastas abaixo. Arquivos em `core/` aparecem como **Core** e os de `suplements/` como **Suplemento**. A IA prefere os Core quando as regras divergem.

```
data/rulebooks/core/
data/rulebooks/suplements/
```

> Os livros oficiais são material protegido por direitos autorais. Use apenas cópias que você possui e evite publicá-los no repositório.

### 4. Indexar os livros (só na primeira vez ou quando mudar os livros)

```bash
python -c "from src.rag_engine import build_vector_store; build_vector_store()"
```

Na primeira execução, o modelo de embeddings é baixado (precisa de internet nesse momento). A indexação lê os arquivos, divide em trechos e grava os vetores em `data/vectordb`, mostrando o progresso e avisando se algum arquivo não puder ser lido. Em CPU, pode levar de dez a trinta minutos.

A base é sempre recriada do zero, então rodar o comando de novo não duplica nada. Se o app já estiver aberto, reinicie-o depois de indexar.

### 5. Iniciar o app

```bash
streamlit run app.py
```

O navegador abre em `http://localhost:8501`. Se o Ollama não estiver rodando, o app tenta iniciá-lo sozinho. Se não conseguir, ele avisa o comando para rodar (`ollama serve`).

---

## 💬 Exemplos de uso

- **Assistente:** "Como funciona a condição Agarrado?", "Crie um NPC estalajadeiro com um segredo", "O que é uma rede neural?"
- **Mestre:** digite `/mestre` (ou "seja meu mestre"), escolha o cenário e a ficha e jogue: "Olho ao redor", "Ataco o esqueleto com a espada", "Tirei 16 no dado".
- **Jogador:** digite `/jogador`, defina o personagem e o perfil, narre a cena ("Vocês entram numa taverna barulhenta") e, ao terminar, use `/feedback`.

## 🔧 Configuração

Os parâmetros ficam em `src/config.py`. O modelo e a janela de contexto também podem ser trocados sem editar o código:

```bash
# Usa outro modelo (baixe antes com: ollama pull llama3.1)
OLLAMA_MODEL=llama3.1 streamlit run app.py

# Janela de contexto, em tokens (padrão: 8192)
OLLAMA_NUM_CTX=4096 streamlit run app.py
```

Mudar `EMBEDDING_MODEL_NAME`, `CHUNK_SIZE` ou `CHUNK_OVERLAP` exige indexar os livros de novo.

---

## 🩺 Solução de problemas

| Problema | O que fazer |
|---|---|
| "Não foi possível usar o Ollama" | Confira se o serviço está no ar (`ollama serve`) e se o modelo foi baixado (`ollama list`; se faltar, `ollama pull llama3`). |
| "Base vetorial não inicializada" | Rode a indexação (passo 4) e reinicie o app. |
| Respostas muito lentas | Em CPU isso é normal para um modelo de 8 bilhões de parâmetros. Feche outros programas pesados ou tente um modelo menor via `OLLAMA_MODEL`, sabendo que a qualidade em português costuma cair. |
| A IA ignora as regras do prompt | Veja o "Prompt Tokens" no painel de métricas. Se estiver perto do valor de `OLLAMA_NUM_CTX`, o prompt está estourando a janela de contexto. |
| A instalação do PyTorch falha | Use o Python 3.12 e instale o PyTorch para CPU antes das demais dependências (passo 2). |

## ⚠️ Limitações conhecidas

- A qualidade depende do Llama 3 de 8B: ele pode errar regras ou contas. Por isso o modo Assistente mostra as fontes, para você conferir.
- O dado do Mestre é sorteado em Python, mas a conta de dano e de PV ainda é feita pelo modelo. O estado do combate também depende de o modelo escrever a linha `[ESTADO]`.
- A ficha do personagem é um texto livre, interpretado pelo modelo.
- O tamanho dos trechos usados na busca ainda não foi validado com testes de recuperação, e a citação indica o livro, ainda não a seção.
- As conversas ficam só na sessão do navegador: ao fechar ou recarregar a página, elas se perdem.

---

# 👥 Autoria

Desenvolvido por Fredson Arthur da Silva Gomes

Projeto de âmbito acadêmico e de investigação focado em Engenharia de Software, Sistemas Operacionais e Aplicações Práticas de Inteligência Artificial Local.