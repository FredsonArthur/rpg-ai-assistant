"""
Módulo 3: IA como Jogador de treino (UC07, UC08, UC09)
------------------------------------------------------
O usuário é o Mestre e a IA interpreta um personagem jogador.

- UC07: perfil (arquétipo) do jogador: Iniciante, Tático, Roleplay ou Personalizado.
  Cada perfil muda o trecho do prompt e a temperatura, e pode ser trocado no meio da sessão.
- UC08: a IA responde como o personagem, no formato [Ação]/[Fala], sem metagame. Por isso este
  módulo NÃO consulta os livros: o personagem só pode saber o que o Mestre descreveu.
- UC09: feedback pedagógico pós-sessão, em que a IA sai do personagem e vira mentora do Mestre.
"""

import re

from src.config import HISTORY_WINDOW, ARCHETYPE_TEMPERATURES, TEMPERATURE_FEEDBACK
from src.rag_engine import chat_llm
from src.prompt_templates import PLAYER_PROMPT, ARCHETYPES, FEEDBACK_PROMPT
from src.dice import bandeja_de_dados
from src.utils import janela_historico

# Perfis oferecidos ao usuário (os três prontos + um texto livre)
ARQUETIPOS_DISPONIVEIS = list(ARCHETYPES) + ["Personalizado"]

PERFIL_NEUTRO = "Jogue de forma equilibrada, de acordo com a personalidade descrita na ficha."
TEMPERATURA_PADRAO = 0.5

# O feedback precisa de pelo menos esta quantidade de falas do Mestre (usuário) para ser útil
MIN_FALAS_MESTRE = 2
AVISO_HISTORICO_CURTO = (
    "A sessão ainda está muito curta para uma avaliação. Continue jogando mais algumas "
    "rodadas e peça o feedback de novo, assim eu consigo analisar melhor a sua condução."
)
# Limite do histórico enviado ao feedback (em caracteres), para caber na janela de contexto
LIMITE_HISTORICO_FEEDBACK = 12000

_RE_ACAO = re.compile(r"\[A[çc][ãa]o\]\s*:", re.IGNORECASE)
_RE_FALA = re.compile(r"\[Fala\]\s*:", re.IGNORECASE)

LEMBRETE_FORMATO = (
    "Sua resposta não seguiu o formato. Responda de novo ao Mestre, em 2 a 4 frases, "
    "exatamente neste formato:\n"
    "[Ação]: o que o personagem faz, em terceira pessoa.\n"
    "[Fala]: \"o que o personagem diz, em primeira pessoa.\""
)

_SAUDACOES = {
    "Iniciante": "Pronto, Mestre! Já estou com a ficha de {nome} aberta aqui. Pode descrever onde meu personagem está e como começamos? Se eu me atrapalhar com alguma regra, me avisa!",
    "Tático": "Pronto, Mestre. {nome} está preparado. Descreva a cena e a posição de todos.",
    "Roleplay": "Pronto, Mestre! {nome} está pronto para entrar na história. Pode descrever a cena e eu faço o resto!",
    "Personalizado": "Pronto, Mestre! Já estou com a ficha de {nome} aberta aqui. Pode descrever onde meu personagem está e como começamos!",
}


def saudacao_inicial(nome: str, arquetipo: str) -> str:
    """Primeira fala do jogador virtual, no tom do perfil escolhido (UC07)."""
    return _SAUDACOES.get(arquetipo, _SAUDACOES["Personalizado"]).format(nome=nome)


def bloco_arquetipo(arquetipo: str, personalizado: str = "") -> str:
    """Texto do perfil de jogador que entra no prompt (UC07, incluindo o perfil livre)."""
    if arquetipo == "Personalizado":
        return personalizado.strip() or PERFIL_NEUTRO
    return ARCHETYPES.get(arquetipo, PERFIL_NEUTRO)


def formato_valido(resposta: str) -> bool:
    """A resposta do jogador precisa ter as duas partes: [Ação]: e [Fala]:."""
    return bool(_RE_ACAO.search(resposta)) and bool(_RE_FALA.search(resposta))


def run_player_simulator_turn(user_input: str, character: str, chat_history: list,
                              arquetipo: str = "Iniciante", arquetipo_personalizado: str = "") -> str:
    """
    Processa um turno do jogador virtual, respondendo à narração do Mestre (user_input).

    chat_history: mensagens anteriores, SEM a mensagem atual.
    O perfil é lido a cada turno, então pode mudar no meio da sessão sem perder o histórico.
    Se a resposta vier fora do formato [Ação]/[Fala], pede uma segunda tentativa.
    Levanta OllamaError se a LLM local estiver indisponível.
    """
    system_prompt = PLAYER_PROMPT.format(
        character=character,
        archetype=bloco_arquetipo(arquetipo, arquetipo_personalizado),
        dados=bandeja_de_dados()
    )

    messages = [{"role": "system", "content": system_prompt}]
    for msg in janela_historico(chat_history, HISTORY_WINDOW):
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_input})

    temperatura = ARCHETYPE_TEMPERATURES.get(arquetipo, TEMPERATURA_PADRAO)
    resposta = chat_llm(messages, temperature=temperatura)['message']['content'].strip()

    if not formato_valido(resposta):
        messages.append({"role": "assistant", "content": resposta})
        messages.append({"role": "user", "content": LEMBRETE_FORMATO})
        segunda = chat_llm(messages, temperature=min(temperatura, 0.4))['message']['content'].strip()
        if formato_valido(segunda):
            resposta = segunda

    return resposta


def historico_suficiente(chat_history: list) -> bool:
    """Indica se já há falas do Mestre suficientes para gerar o feedback (UC09, FA01)."""
    return sum(1 for msg in chat_history if msg["role"] == "user") >= MIN_FALAS_MESTRE


def formatar_historico(chat_history: list, limite: int = LIMITE_HISTORICO_FEEDBACK) -> str:
    """Transforma o histórico em texto para o prompt de feedback, mantendo o trecho mais recente."""
    linhas = []
    for msg in chat_history:
        autor = "Mestre (usuário)" if msg["role"] == "user" else "Jogador (IA)"
        linhas.append(f"{autor}: {msg['content']}")
    texto = "\n\n".join(linhas)
    if len(texto) > limite:
        texto = "[início da sessão omitido]\n" + texto[-limite:]
    return texto


def gerar_feedback(chat_history: list) -> str:
    """
    UC09: a IA sai do personagem e analisa a condução do Mestre (o usuário).
    Com histórico curto demais, devolve um aviso em vez de chamar o modelo (FA01).
    O feedback NÃO entra no histórico da sessão, então o jogo continua de onde parou (FA02).
    Levanta OllamaError se a LLM local estiver indisponível.
    """
    if not historico_suficiente(chat_history):
        return AVISO_HISTORICO_CURTO

    messages = [
        {"role": "system", "content": FEEDBACK_PROMPT.format(history=formatar_historico(chat_history))},
        {"role": "user", "content": "Gere o feedback da sessão, seguindo as 3 partes."}
    ]
    return chat_llm(messages, temperature=TEMPERATURE_FEEDBACK)['message']['content'].strip()