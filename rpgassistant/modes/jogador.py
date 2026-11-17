"""
Modo Jogador: IA como Jogador de treino (UC07, UC08, UC09)
------------------------------------------------------
O usuário é o Mestre e a IA interpreta um personagem jogador.

- UC07: perfil (arquétipo) do jogador: Iniciante, Tático, Roleplay ou Personalizado.
  Cada perfil muda o trecho do prompt e a temperatura, e pode ser trocado no meio da sessão.
- UC08: a IA responde como o personagem, no formato [Ação]/[Fala], sem metagame. Por isso este
  modo NÃO consulta os livros: o personagem só pode saber o que o Mestre descreveu.
- UC09: feedback pedagógico pós-sessão, em que a IA sai do personagem e vira mentora do Mestre.

A fala do jogador e o feedback chegam em streaming (`run_player_simulator_turn_stream` e
`iniciar_feedback_stream`), como nos outros modos, para o botão Parar interromper a resposta. As
versões sem streaming (`run_player_simulator_turn` e `gerar_feedback`) continuam disponíveis.
"""

import re
from typing import Iterator, List

from rpgassistant import config
from rpgassistant.core.historico import Historico, Mensagem, janela_historico
from rpgassistant.services import llm
from rpgassistant.services.dados import bandeja_de_dados
from rpgassistant.services.prompts import ARCHETYPES, FEEDBACK_PROMPT, PLAYER_PROMPT

# Perfis oferecidos ao usuário (os três prontos + um texto livre)
ARQUETIPOS_DISPONIVEIS = list(ARCHETYPES) + ["Personalizado"]

FICHA_PADRAO = "Maga Elfa, Nível 1, PV 8, Inteligência +3, Destreza +2. Curiosa, gentil e um pouco medrosa."
PERFIL_NEUTRO = "Jogue de forma equilibrada, de acordo com a personalidade descrita na ficha."

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


def _montar_mensagens(user_input: str, character: str, chat_history: Historico,
                      arquetipo: str, arquetipo_personalizado: str) -> List[Mensagem]:
    """
    Monta as mensagens de um turno do jogador: o prompt do sistema (ficha, perfil e dados sorteados), o
    histórico recente (preservando a abertura da cena) e, por último, a fala do Mestre. É usada tanto
    pela versão com streaming quanto pela sem streaming, para as duas montarem exatamente o mesmo prompt.
    """
    system_prompt = PLAYER_PROMPT.format(
        character=character,
        archetype=bloco_arquetipo(arquetipo, arquetipo_personalizado),
        dados=bandeja_de_dados()
    )

    mensagens: List[Mensagem] = [{"role": "system", "content": system_prompt}]
    for msg in janela_historico(chat_history, config.settings.history_window):
        mensagens.append({"role": msg["role"], "content": msg["content"]})
    mensagens.append({"role": "user", "content": user_input})
    return mensagens


def run_player_simulator_turn(user_input: str, character: str, chat_history: Historico,
                              arquetipo: str = "Iniciante", arquetipo_personalizado: str = "") -> str:
    """
    Processa um turno do jogador virtual, respondendo à narração do Mestre (user_input).
    Versão sem streaming: devolve a fala inteira de uma vez (a interface usa a versão com streaming,
    `run_player_simulator_turn_stream`).

    chat_history: mensagens anteriores, SEM a mensagem atual.
    O perfil é lido a cada turno, então pode mudar no meio da sessão sem perder o histórico.
    Se a resposta vier fora do formato [Ação]/[Fala], pede uma segunda tentativa.
    Levanta OllamaError se a LLM local estiver indisponível.
    """
    mensagens = _montar_mensagens(user_input, character, chat_history, arquetipo, arquetipo_personalizado)

    temperatura = config.settings.temperatura_do_arquetipo(arquetipo)
    resposta = llm.chat_llm(mensagens, temperature=temperatura)['message']['content'].strip()

    if not formato_valido(resposta):
        mensagens.append({"role": "assistant", "content": resposta})
        mensagens.append({"role": "user", "content": LEMBRETE_FORMATO})
        segunda = llm.chat_llm(mensagens, temperature=min(temperatura, 0.4))['message']['content'].strip()
        if formato_valido(segunda):
            resposta = segunda

    return resposta


class RespostaDoJogadorEmStream:
    """
    Fala do jogador virtual chegando em streaming, com a conferência do formato [Ação]/[Fala] no fim.

    Itere `tokens()` para receber os pedaços. `texto` guarda sempre a fala que vale NO MOMENTO:
    - durante a geração, é o que já chegou da tentativa em curso;
    - se a primeira tentativa vier fora do formato, `tokens()` entrega um pedaço vazio ("") para avisar
      que a tela deve ser limpa, `texto` volta a ficar vazio e a segunda tentativa é transmitida;
    - se a segunda também vier fora do formato, `texto` volta a ser a primeira fala (como na versão sem
      streaming, que mantém a primeira).
    Por isso, quem consome este objeto deve ler `texto`, e não somar os pedaços recebidos.
    Falhas de comunicação com o Ollama levantam OllamaError durante a iteração.
    """

    def __init__(self, mensagens: List[Mensagem], temperatura: float) -> None:
        self._mensagens = mensagens
        self._temperatura = temperatura
        self.texto = ""

    def tokens(self) -> Iterator[str]:
        """Entrega a fala aos poucos. Nada é enviado ao modelo antes de começar a iterar."""
        # 1ª tentativa: cada pedaço é repassado assim que chega.
        primeira = llm.chat_llm_stream(self._mensagens, temperature=self._temperatura)
        for parte in primeira.tokens():
            self.texto = primeira.texto
            yield parte
        if formato_valido(primeira.texto):
            return

        # Fora do formato: limpa a tela e pede de novo, lembrando o formato ao modelo.
        self.texto = ""
        yield ""
        refazer = self._mensagens + [
            {"role": "assistant", "content": primeira.texto.strip()},
            {"role": "user", "content": LEMBRETE_FORMATO},
        ]
        segunda = llm.chat_llm_stream(refazer, temperature=min(self._temperatura, 0.4))
        for parte in segunda.tokens():
            self.texto = segunda.texto
            yield parte
        if not formato_valido(segunda.texto):
            self.texto = primeira.texto  # a segunda também falhou: mantém a primeira


def run_player_simulator_turn_stream(user_input: str, character: str, chat_history: Historico,
                                     arquetipo: str = "Iniciante",
                                     arquetipo_personalizado: str = "") -> RespostaDoJogadorEmStream:
    """
    Como `run_player_simulator_turn`, mas a fala chega em streaming (veja RespostaDoJogadorEmStream),
    o que permite interromper a geração no meio (botão Parar).

    chat_history: mensagens anteriores, SEM a mensagem atual.
    Só monta o prompt: o modelo é chamado quando `tokens()` começa a ser iterado, e é nesse momento
    que um OllamaError pode ser levantado.
    """
    mensagens = _montar_mensagens(user_input, character, chat_history, arquetipo, arquetipo_personalizado)
    return RespostaDoJogadorEmStream(mensagens, config.settings.temperatura_do_arquetipo(arquetipo))


def historico_suficiente(chat_history: Historico) -> bool:
    """Indica se já há falas do Mestre suficientes para gerar o feedback (UC09, FA01)."""
    return sum(1 for msg in chat_history if msg["role"] == "user") >= MIN_FALAS_MESTRE


def formatar_historico(chat_history: Historico, limite: int = LIMITE_HISTORICO_FEEDBACK) -> str:
    """Transforma o histórico em texto para o prompt de feedback, mantendo o trecho mais recente."""
    linhas = []
    for msg in chat_history:
        autor = "Mestre (usuário)" if msg["role"] == "user" else "Jogador (IA)"
        linhas.append(f"{autor}: {msg['content']}")
    texto = "\n\n".join(linhas)
    if len(texto) > limite:
        texto = "[início da sessão omitido]\n" + texto[-limite:]
    return texto


def _mensagens_do_feedback(chat_history: Historico) -> List[Mensagem]:
    """Mensagens do pedido de feedback: o prompt do mentor, com o histórico da sessão, e a instrução final."""
    return [
        {"role": "system", "content": FEEDBACK_PROMPT.format(history=formatar_historico(chat_history))},
        {"role": "user", "content": "Gere o feedback da sessão, seguindo as 3 partes."}
    ]


def gerar_feedback(chat_history: Historico) -> str:
    """
    UC09: a IA sai do personagem e analisa a condução do Mestre (o usuário).
    Versão sem streaming (a interface usa `iniciar_feedback_stream`).
    Com histórico curto demais, devolve um aviso em vez de chamar o modelo (FA01).
    O feedback NÃO entra no histórico da sessão, então o jogo continua de onde parou (FA02).
    Levanta OllamaError se a LLM local estiver indisponível.
    """
    if not historico_suficiente(chat_history):
        return AVISO_HISTORICO_CURTO

    messages = _mensagens_do_feedback(chat_history)
    return llm.chat_llm(messages, temperature=config.settings.temperatura_feedback)['message']['content'].strip()


def iniciar_feedback_stream(chat_history: Historico) -> llm.RespostaEmStream:
    """
    UC09 com streaming: devolve o feedback chegando aos poucos, para a interface mostrá-lo enquanto é
    escrito e permitir interromper (botão Parar).
    Não confere o tamanho do histórico: quem chama deve usar `historico_suficiente` antes (o controlador
    já faz isso e mostra `AVISO_HISTORICO_CURTO` quando a sessão ainda está curta).
    Levanta OllamaError se a LLM local estiver indisponível.
    """
    return llm.chat_llm_stream(_mensagens_do_feedback(chat_history), temperature=config.settings.temperatura_feedback)