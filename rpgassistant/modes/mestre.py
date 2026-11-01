"""
Modo Mestre: IA como Mestre de treino (UC04, UC05, UC06)
-----------------------------------------------------
A IA conduz uma aventura solo (One-on-One), processa as ações do jogador, pede testes de
dados com base nas regras (RAG) e gerencia combates.

Para o combate ser confiável, o módulo não depende só da memória do modelo:
- Dados: os sorteios dos monstros vêm de uma "bandeja" rolada em Python (rpgassistant/services/dados.py).
- Estado: o Mestre termina as falas de combate com uma linha "[ESTADO] ..." (PV, CA).
  O módulo guarda essa linha e a devolve ao modelo em todos os turnos, mesmo quando o
  histórico antigo já saiu da janela de contexto.
"""

import re
from typing import Tuple

from rpgassistant import config
from rpgassistant.core.historico import Historico, janela_historico
from rpgassistant.services import llm, rag
from rpgassistant.services.dados import bandeja_de_dados
from rpgassistant.services.prompts import MASTER_PROMPT

# Opções oferecidas ao configurar uma aventura
CENARIOS = [
    "Masmorra nas Ruínas de uma Tumba Antiga",
    "Investigação Urbana em uma Taverna Assombrada",
    "Floresta Sombria e Pântano dos Goblins",
    "Covil do Dragão Jovem nas Montanhas Geladas",
]
FICHA_PADRAO = "Guerreiro Humano, Nível 2 (Espada Curta, Escudo, Cota de Malha)"
FICHA_GENERICA = "Guerreiro Humano, Nível 1"  # usada quando o usuário deixa a ficha em branco (UC04, FA01)

# Linha de estado no fim da fala do Mestre, ex.: "[ESTADO] Jogador PV 12/15 | Goblin PV 3/7 CA 15"
_RE_ESTADO = re.compile(r"^[ \t]*\[ESTADO\][ \t]*:?[ \t]*(.*?)[ \t]*$", re.IGNORECASE | re.MULTILINE)


def montar_consulta(user_input: str, chat_history: Historico) -> str:
    """
    Monta a consulta ao RAG. Mensagens como "Tirei 16 no dado" não dizem nada sobre o assunto,
    então a ação do jogador vem acompanhada do fim da última fala do Mestre (onde ele pediu o
    teste ou citou o monstro). A ação vai primeiro porque o modelo de embeddings lê só o
    começo do texto.
    """
    ultima_fala_mestre = ""
    for msg in reversed(chat_history):
        if msg["role"] == "assistant":
            ultima_fala_mestre = msg["content"][-250:]
            break
    return f"{user_input}. {ultima_fala_mestre}".strip()


def extrair_estado(resposta: str, estado_anterior: str = "") -> Tuple[str, str]:
    """
    Separa a linha "[ESTADO] ..." do texto da fala do Mestre.
    Retorna (texto sem a linha, novo estado):
    - sem a linha na resposta, o estado anterior continua valendo;
    - "[ESTADO] Sem combate" limpa o estado.
    """
    encontrados = list(_RE_ESTADO.finditer(resposta))
    if not encontrados:
        return resposta.strip(), estado_anterior

    estado = encontrados[-1].group(1).strip()
    texto = _RE_ESTADO.sub("", resposta)
    texto = re.sub(r"\n{3,}", "\n\n", texto).strip()

    if not estado or estado.lower().startswith(("sem combate", "nenhum")):
        estado = ""
    return texto, estado


def ocultar_linha_estado(texto: str) -> str:
    """
    Esconde a linha "[ESTADO] ..." (inclusive pela metade) de um texto que ainda está chegando
    em streaming, para o usuário não ver o marcador surgindo letra por letra.
    """
    achado = re.search(r"^[ \t]*\[ESTADO\]", texto, re.IGNORECASE | re.MULTILINE)
    if achado:
        return texto[:achado.start()].rstrip()

    ultimo = texto.rfind("[")
    if ultimo != -1:
        inicio_linha = texto.rfind("\n", 0, ultimo) + 1
        comeco_de_linha = texto[inicio_linha:ultimo].strip() == ""
        if comeco_de_linha and "[estado]".startswith(texto[ultimo:].lower()):
            return texto[:inicio_linha].rstrip()
    return texto


def _preparar_turno(user_input: str, scenario: str, character: str,
                    chat_history: Historico, estado: str) -> Tuple[list, str]:
    """Busca nos livros, sorteia os dados e monta as mensagens do turno. Retorna (mensagens, fontes)."""
    # 1. Busca nos livros usando a ação do jogador + o fim da última fala do Mestre
    contexto, fontes = rag.recuperar_contexto(montar_consulta(user_input, chat_history), k=config.settings.top_k_mestre)

    # 2. Prompt do sistema: sessão, estado de combate, dados sorteados e contexto das regras
    system_prompt = MASTER_PROMPT.format(
        scenario=scenario,
        character=character,
        estado=estado or "Sem combate em andamento.",
        dados=bandeja_de_dados(),
        context=contexto
    )

    # 3. Mensagens: system + histórico (abertura da cena + mais recentes) + ação atual
    messages = [{"role": "system", "content": system_prompt}]
    for msg in janela_historico(chat_history, config.settings.history_window):
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_input})
    return messages, fontes


def run_master_turn_stream(user_input: str, scenario: str, character: str,
                           chat_history: Historico, estado: str = "") -> Tuple[llm.RespostaEmStream, str]:
    """
    Processa um turno do Mestre virtual e devolve (stream, fontes): a fala chega em streaming.

    chat_history: mensagens anteriores, SEM a mensagem atual (user_input).
    estado: estado de combate vigente (a linha [ESTADO] do turno anterior), ou "".
    Levanta OllamaError se a LLM local estiver indisponível.
    Quando o stream terminar, passe `stream.texto` para extrair_estado() para separar a fala
    do novo estado; durante o streaming, use ocultar_linha_estado() para exibir o texto.
    """
    messages, fontes = _preparar_turno(user_input, scenario, character, chat_history, estado)
    return llm.chat_llm_stream(messages, temperature=config.settings.temperatura_mestre), fontes