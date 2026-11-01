# 🎲 RPG AI Assistant (D&D 5e)

> Um aplicativo de desktop com IA que roda **100% no seu computador**, sem internet depois da instalação, para apoiar Mestres e Jogadores de *Dungeons & Dragons 5e* (edições 2024/2025). Ele responde dúvidas **somente com o que está nos seus livros**, e, quando você pede, **vira o Mestre** de uma aventura ou **um jogador** para você treinar.

Projeto da disciplina **Tópicos Especiais em Inteligência Artificial**: um LLM local aplicado a um problema real, usando tokenização, embeddings, Transformer, engenharia de prompt e RAG.

---

## ✨ O que ele faz

O app tem **vários chats**, todos salvos no seu computador. Ao fechar e abrir de novo, as conversas voltam como estavam. Cada chat tem **um modo fixo**, escolhido na **primeira mensagem**:

| Modo | O que a IA faz | Como pedir na primeira mensagem |
|---|---|---|
| 🧙 **Assistente** | Responde dúvidas de regras e lore e cria NPCs, encontros e itens **apenas com base nos livros indexados**, citando a fonte. Se o assunto não estiver nos livros, diz que não dá para responder. | `1`, `assistente`, ou já uma pergunta de regras |
| 🗺️ **Mestre** | Conduz uma aventura solo: descreve a cena, pede testes com a CD adequada, controla monstros e combates. Você joga. | `2`, `mestre`, `/mestre` ou "seja meu mestre" |
| ⚔️ **Jogador** | Interpreta um personagem (perfil Iniciante, Tático, Roleplay ou Personalizado). Você é o Mestre e narra a cena. | `3`, `jogador`, `/jogador` ou "quero ser o mestre" |

Para usar outro modo, abra um novo chat. Dentro de um chat existem dois comandos: `/ajuda` e `/feedback` (no modo Jogador, a IA sai do personagem e analisa a sua condução como Mestre).

### Destaques

- **Só os livros:** a pergunta é recusada antes de chegar ao modelo se o melhor trecho encontrado não for parecido o bastante (limiar de relevância). Se passar, o modelo ainda só pode usar o contexto e responde `NAO_ENCONTRADO` quando a resposta não está lá.
- **Respostas com fonte:** cada resposta do Assistente mostra os livros usados (marcados como *Core* ou *Suplemento*) e a contagem de tokens.
- **Memória de conversa:** perguntas como "e se eu estiver cego?" são reescritas com o contexto anterior antes da busca nos livros.
- **Combate confiável:** os dados dos monstros são sorteados em Python (a IA não "inventa" rolagens), e o estado do combate (PV e CA) é guardado e devolvido ao Mestre a cada turno.
- **Jogador sem metagame:** a IA jogadora não consulta os livros; ela só sabe o que você narrou.
- **Janela que não trava:** o modelo roda em segundo plano, as respostas aparecem aos poucos e há um botão **Parar**.
- **Erros sem perda:** se o Ollama falhar, a pergunta volta para a caixa de texto e não fica no histórico.

---

## 🧠 Conceitos de IA aplicados

| Conceito | Onde aparece no projeto |
|---|---|
| **Tokenização** | O modelo trabalha com tokens, e a janela de contexto é limitada (`OLLAMA_NUM_CTX`). Cada resposta do Assistente mostra os tokens do prompt e da resposta. |
| **Embeddings** | Os trechos dos livros viram vetores com `paraphrase-multilingual-MiniLM-L12-v2`, guardados no ChromaDB. A pergunta também vira um vetor, e a busca traz os trechos mais próximos. A mesma similaridade decide se a pergunta é do assunto dos livros. |
| **Transformer** | O Llama 3 (via Ollama) e o modelo de embeddings são baseados em Transformers. O app controla a geração com a temperatura (por modo e por perfil de jogador) e com a janela de contexto. |
| **Engenharia de prompt** | Todos os prompts ficam em `rpgassistant/services/prompts.py`: papéis, regras de conduta, contexto delimitado, formato de saída obrigatório, exemplo de resposta, código de recusa (`NAO_ENCONTRADO`) e reescrita da pergunta. |
| **RAG** | Livros → trechos → embeddings → busca por similaridade → barreira de relevância → contexto no prompt → resposta com fonte. |

---

## ⚙️ Como funciona

```
 Janela (PySide6) ──► core/controller.py  (lógica de cada chat: modo, turnos, feedback)
   ui/                     │
                           ├── core/mode_selection.py  (primeira mensagem)
                           ├── core/policy.py          (política "só os livros")
                           ├── core/chats.py ──► storage/ (SQLite: data/chats.db)
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
 modes/assistente.py  modes/mestre.py   modes/jogador.py
        │                  │                  │
        └─► services/rag.py (busca) ◄─┘       │   (o Jogador não usa os livros)
                 │                            │
             ChromaDB                  services/llm.py ──► Ollama (Llama 3)
        (data/vectordb)
```

## 🛠️ Stack

- **Linguagem:** Python 3.10+
- **Interface:** PySide6 (Qt), janela nativa e offline
- **LLM local:** Ollama com `llama3`
- **RAG:** LangChain (leitura e divisão de texto) e ChromaDB
- **Embeddings:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- **Conversas:** SQLite (biblioteca padrão do Python)

## 📁 Estrutura do projeto

```
rpg-ai-assistant/
├── main.py                     # Abre a janela:  python main.py
├── requirements.txt
├── pyproject.toml              # Metadados do projeto e configuração do ruff
├── data/
│   ├── rulebooks/              # Seus livros (.md ou .pdf)
│   │   ├── core/               # Livros Core (ex.: Livro do Jogador, Manual dos Monstros)
│   │   └── suplements/         # Suplementos e guias
│   ├── vectordb/               # Base vetorial gerada (não vai para o GitHub)
│   └── chats.db                # Suas conversas (não vai para o GitHub)
├── rpgassistant/
│   ├── config.py               # Configuração tipada: caminhos, RAG, modelo, limiar e temperaturas
│   ├── errors.py               # Erros do domínio (OllamaError, BaseVaziaError...)
│   ├── logs.py                 # Configuração dos logs
│   ├── indexar.py              # Indexa os livros:  python -m rpgassistant.indexar
│   ├── calibrar.py             # Calibra o limiar:  python -m rpgassistant.calibrar
│   ├── core/
│   │   ├── controller.py       # Lógica de cada chat nos três modos
│   │   ├── chats.py            # Criar, abrir, renomear, excluir e restaurar chats
│   │   ├── models.py           # Chat e mensagens salvas
│   │   ├── mode_selection.py   # Interpreta a primeira mensagem
│   │   ├── policy.py           # Política "só os livros"
│   │   ├── modos.py            # Os três modos e a leitura de pedidos
│   │   └── historico.py        # Janela de histórico enviada ao modelo
│   ├── modes/
│   │   ├── assistente.py       # Modo Assistente
│   │   ├── mestre.py           # Modo Mestre
│   │   └── jogador.py          # Modo Jogador e feedback pós-sessão
│   ├── services/
│   │   ├── llm.py              # Chamadas ao Ollama (inteira e em streaming)
│   │   ├── rag.py              # Indexação, busca nos livros e reescrita da pergunta
│   │   ├── prompts.py          # Todos os prompts do sistema
│   │   ├── dados.py            # Dados sorteados em Python
│   │   └── ollama_service.py   # Verifica e inicia o servidor do Ollama
│   ├── storage/
│   │   ├── database.py         # Banco SQLite: esquema, migrações e transações
│   │   └── repository.py       # Leitura e gravação de chats e mensagens
│   └── ui/                     # Janela, bolhas de mensagem, diálogos, threads e tema
└── tests/                      # Testes automatizados
```

---

## 🚀 Como executar

### 1. Pré-requisitos

- **Python 3.10 ou superior.** Se a instalação do PyTorch ou do PySide6 falhar em uma versão muito recente do Python, use o Python 3.12.
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
python -m rpgassistant.indexar
```

Na primeira execução, o modelo de embeddings é baixado (precisa de internet nesse momento). A indexação lê os arquivos, divide em trechos e grava os vetores em `data/vectordb`, mostrando o progresso e avisando se algum arquivo não puder ser lido. Em CPU, pode levar de dez a trinta minutos. A base é sempre recriada do zero, então rodar o comando de novo não duplica nada.

### 5. Calibrar o limiar do Assistente (recomendado)

O Assistente recusa perguntas cujo melhor trecho tenha similaridade abaixo de `relevancia_minima`. O valor padrão (0.30) é só um palpite, e o ideal depende dos seus livros. Para medir:

```bash
python -m rpgassistant.calibrar
```

O script roda perguntas de dentro e de fora do tema, mostra a similaridade de cada uma e sugere o limiar que melhor separa os dois grupos. Você também pode usar as suas próprias perguntas (uma por linha) com `--dentro arquivo.txt` e `--fora arquivo.txt`. Para aplicar o valor sugerido:

```bash
RPG_RELEVANCIA_MINIMA=0.35 python main.py
```

(ou troque o padrão `relevancia_minima` em `rpgassistant/config.py`).

### 6. Abrir o app

```bash
python main.py
```

Se o Ollama não estiver rodando, o app tenta iniciá-lo sozinho. Se não conseguir, a barra de status avisa o comando para rodar (`ollama serve`).

---

## 💬 Exemplos de uso

- **Assistente:** "Como funciona a condição Agarrado?", "Crie um NPC estalajadeiro". Uma pergunta como "O que é uma rede neural?" será recusada, porque não está nos livros.
- **Mestre:** em um chat novo, digite `2` (ou "seja meu mestre"), escolha o cenário e a ficha e jogue: "Olho ao redor", "Ataco o esqueleto com a espada", "Tirei 16 no dado".
- **Jogador:** em um chat novo, digite `3`, defina o personagem e o perfil, narre a cena ("Vocês entram numa taverna barulhenta") e, ao terminar, use `/feedback` ou o botão de feedback.

**Atalhos:** `Ctrl+N` novo chat · `F2` renomear · botão direito na lista para renomear ou excluir · `Enter` envia e `Shift+Enter` quebra a linha.

## 🔧 Configuração

Os parâmetros ficam em `rpgassistant/config.py`. Estes podem ser trocados sem editar o código, por variável de ambiente:

| Variável | O que muda | Padrão |
|---|---|---|
| `OLLAMA_MODEL` | Modelo do Ollama (baixe antes com `ollama pull`) | `llama3` |
| `OLLAMA_NUM_CTX` | Janela de contexto, em tokens | `8192` |
| `RPG_RELEVANCIA_MINIMA` | Limiar de relevância do Assistente (0 a 1; 0 desliga a barreira) | `0.30` |
| `RPG_DATA_DIR` | Pasta de dados (livros, base vetorial e conversas) | `data/` do projeto |

```bash
OLLAMA_MODEL=llama3.1 python main.py
```

Mudar `embedding_model`, `chunk_size` ou `chunk_overlap` em `config.py` exige indexar os livros de novo.

---

## 🧪 Testes

```bash
python -m unittest discover -s tests -t .
```

Os testes simulam o Ollama, a base vetorial e o Qt, então rodam sem o Ollama, sem os livros indexados e sem abrir janela. Se o PySide6 estiver instalado, `tests/test_ui_qt.py` também roda a janela de verdade, em modo `offscreen`.

---

## 🩺 Solução de problemas

| Problema | O que fazer |
|---|---|
| "Não foi possível usar o Ollama" | Confira se o serviço está no ar (`ollama serve`) e se o modelo foi baixado (`ollama list`; se faltar, `ollama pull llama3`). |
| "A base de livros ainda não foi indexada" | Rode `python -m rpgassistant.indexar` e reabra o app. |
| O Assistente recusa perguntas que deveria responder | O limiar está alto demais para os seus livros. Rode `python -m rpgassistant.calibrar` e ajuste `RPG_RELEVANCIA_MINIMA`. |
| O Assistente responde perguntas fora do tema | O limiar está baixo demais. Calibre como acima. |
| Erro "Could not load the Qt platform plugin xcb" (Linux) | Falta uma biblioteca do sistema: no Fedora, `sudo dnf install xcb-util-cursor`; no Ubuntu e no Debian, `sudo apt install libxcb-cursor0`. |
| Respostas muito lentas | Em CPU isso é normal para um modelo de 8 bilhões de parâmetros. Feche outros programas pesados ou tente um modelo menor via `OLLAMA_MODEL`, sabendo que a qualidade em português costuma cair. |
| A IA ignora as regras do prompt | Veja o "Prompt Tokens" no rodapé da resposta. Se estiver perto do valor de `OLLAMA_NUM_CTX`, o prompt está estourando a janela de contexto. |
| "Não foi possível abrir o banco de chats" | O arquivo `data/chats.db` está danificado ou é de uma versão mais nova. Renomeie-o para guardar uma cópia e abra o app de novo (ele cria um banco novo). |
| A instalação do PyTorch ou do PySide6 falha | Use o Python 3.12 e instale o PyTorch para CPU antes das demais dependências (passo 2). |

## ⚠️ Limitações conhecidas

- A qualidade depende do Llama 3 de 8B: ele pode errar regras ou contas. Por isso o Assistente mostra as fontes, para você conferir.
- O Assistente só responde o que os livros indexados cobrem; uma pergunta de RPG que não esteja neles também é recusada.
- O limiar de relevância precisa ser calibrado com os seus livros, e o tamanho dos trechos usados na busca ainda não foi validado com testes de recuperação. A citação indica o livro, ainda não a seção.
- O dado do Mestre é sorteado em Python, mas a conta de dano e de PV ainda é feita pelo modelo. O estado do combate também depende de o modelo escrever a linha `[ESTADO]`.
- A ficha do personagem é um texto livre, interpretado pelo modelo.
- Cada chat tem um modo fixo; para trocar, abra outro chat.

---

# 👥 Autoria

Desenvolvido por Fredson Arthur da Silva Gomes

Projeto de âmbito acadêmico e de investigação focado em Engenharia de Software, Sistemas Operacionais e Aplicações Práticas de Inteligência Artificial Local.