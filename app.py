"""
Interface Gráfica Principal (Streamlit) - RPG Tabletop AI Assistant
-------------------------------------------------------------------
Um chat único com três modos de uso (a lógica de decisão está em src/assistant.py):

- Assistente: tira dúvidas sobre qualquer assunto (regras e lore de D&D com apoio dos livros).
- Mestre: a IA conduz uma aventura solo e o usuário joga.
- Jogador: o usuário é o Mestre e a IA interpreta um personagem.

O modo troca pelo menu lateral, por comandos (/mestre, /jogador, /assistente) ou, no modo
Assistente, por pedidos como "seja meu mestre". As respostas do Assistente e do Mestre chegam
em streaming, e tudo roda localmente, via Ollama.
"""

import streamlit as st

from src.assistant import (
    MODO_ASSISTENTE, MODO_MESTRE, MODO_JOGADOR, MODOS, ROTULOS_MODO, AJUDA,
    interpretar_entrada, historico_para_llm,
)
from src.config import OLLAMA_MODEL
from src.ollama_service import ollama_ativo, iniciar_ollama
from src.rag_engine import OllamaError, formatar_metricas
from src.modules.module1_tutor import run_module1_chat_stream
from src.modules.module2_master import (
    run_master_turn, run_master_turn_stream, extrair_estado, ocultar_linha_estado,
)
from src.modules.module3_player import (
    run_player_simulator_turn,
    gerar_feedback,
    historico_suficiente,
    saudacao_inicial,
    ARQUETIPOS_DISPONIVEIS,
    AVISO_HISTORICO_CURTO,
)

st.set_page_config(
    page_title="RPG Tabletop AI Assistant",
    page_icon="🎲",
    layout="wide"
)

# ==========================================
# TEXTOS E CONSTANTES DA INTERFACE
# ==========================================
AVATARES = {MODO_ASSISTENTE: "🧙", MODO_MESTRE: "🗺️", MODO_JOGADOR: "⚔️"}

DESCRICOES = {
    MODO_ASSISTENTE: "Tire dúvidas sobre regras e lore de D&D, peça NPCs, encontros e itens, ou pergunte qualquer outra coisa. "
                     "Diga \"seja meu mestre\" ou \"quero ser o mestre\" (ou use /mestre e /jogador) para jogar. Veja os comandos com /ajuda.",
    MODO_MESTRE: "A IA é o Mestre de uma aventura solo: descreva as suas ações, role os dados quando ele pedir e informe o resultado.",
    MODO_JOGADOR: "Você é o Mestre: narre a cena e a IA responde como um jogador, no perfil escolhido. Ao final, peça um feedback com /feedback.",
}

PLACEHOLDERS = {
    MODO_ASSISTENTE: "Pergunte sobre regras, lore, crie um NPC... ou diga \"seja meu mestre\"",
    MODO_MESTRE: "Descreva a sua ação (ex.: 'Olho ao redor', 'Ataco o esqueleto', 'Tirei 16 no dado')",
    MODO_JOGADOR: "Narre a cena ou fale com o jogador (ex.: 'Vocês entram numa taverna barulhenta.')",
}
PLACEHOLDER_CONFIGURAR = "Configure a sessão acima para começar (ou digite /assistente para voltar)"

CENARIOS = [
    "Masmorra nas Ruínas de uma Tumba Antiga",
    "Investigação Urbana em uma Taverna Assombrada",
    "Floresta Sombria e Pântano dos Goblins",
    "Covil do Dragão Jovem nas Montanhas Geladas",
]
FICHA_MESTRE_PADRAO = "Guerreiro Humano, Nível 2 (Espada Curta, Escudo, Cota de Malha)"
FICHA_GENERICA = "Guerreiro Humano, Nível 1"  # usada se o usuário deixar a ficha em branco
FICHA_JOGADOR_PADRAO = "Maga Elfa, Nível 1, PV 8, Inteligência +3, Destreza +2. Curiosa, gentil e um pouco medrosa."


# ==========================================
# ESTADO DA SESSÃO
# ==========================================
def iniciar_estado() -> None:
    """Cria no estado da sessão tudo o que o app usa, sem sobrescrever o que já existe."""
    padroes = {
        "mensagens": [],                 # chat único: falas e avisos de todos os modos
        "modo": MODO_ASSISTENTE,
        "mudou_modo_por_codigo": False,  # faz o seletor lateral acompanhar uma troca feita por comando
        "ollama_tentado": False,
        # Mestre
        "mestre_ativo": False, "mestre_sessao": 0,
        "mestre_cenario": "", "mestre_personagem": "", "mestre_estado": "",
        # Jogador
        "jogador_ativo": False, "jogador_sessao": 0,
        "jogador_nome": "", "jogador_ficha": "",
        "jogador_arquetipo": ARQUETIPOS_DISPONIVEIS[0], "jogador_arquetipo_texto": "",
    }
    for chave, valor in padroes.items():
        st.session_state.setdefault(chave, valor)


def sessao_do_modo(modo: str) -> int:
    """Cada nova aventura ou personagem abre uma sessão nova, e o histórico antigo deixa de ir ao modelo."""
    return {MODO_MESTRE: st.session_state.mestre_sessao,
            MODO_JOGADOR: st.session_state.jogador_sessao}.get(modo, 0)


def precisa_configurar() -> bool:
    modo = st.session_state.modo
    return (modo == MODO_MESTRE and not st.session_state.mestre_ativo) or \
           (modo == MODO_JOGADOR and not st.session_state.jogador_ativo)


def adicionar_mensagem(role: str, conteudo: str, modo: str, **extras) -> None:
    st.session_state.mensagens.append(
        {"role": role, "content": conteudo, "mode": modo, "sessao": sessao_do_modo(modo), **extras}
    )


def adicionar_aviso(conteudo: str, tipo: str = "modo") -> None:
    """Aviso exibido no chat mas nunca enviado ao modelo (troca de modo, ajuda, feedback)."""
    st.session_state.mensagens.append(
        {"role": "sistema", "kind": tipo, "content": conteudo, "mode": None, "sessao": 0}
    )


def trocar_modo(novo: str) -> None:
    if novo == st.session_state.modo:
        return
    st.session_state.modo = novo
    st.session_state.mudou_modo_por_codigo = True
    adicionar_aviso(f"🔀 Modo alterado para **{ROTULOS_MODO[novo]}**. Para voltar, use /assistente ou o menu lateral.")


def encerrar_aventura() -> None:
    st.session_state.mestre_ativo = False
    st.session_state.mestre_estado = ""


def encerrar_personagem() -> None:
    st.session_state.jogador_ativo = False


def limpar_tudo() -> None:
    st.session_state.mensagens = []
    encerrar_aventura()
    encerrar_personagem()
    st.session_state.modo = MODO_ASSISTENTE
    st.session_state.mudou_modo_por_codigo = True


def garantir_ollama() -> None:
    """Tenta iniciar o Ollama uma vez por sessão; se continuar fora do ar, avisa o usuário."""
    if ollama_ativo():
        return
    if not st.session_state.ollama_tentado:
        st.session_state.ollama_tentado = True
        with st.spinner("Iniciando o Ollama..."):
            iniciar_ollama()
    if not ollama_ativo():
        st.warning("O Ollama não está rodando. Inicie-o com `ollama serve` (e baixe o modelo com "
                   f"`ollama pull {OLLAMA_MODEL}`, se ainda não fez).")


# ==========================================
# EXIBIÇÃO
# ==========================================
def exibir_mensagem(m: dict) -> None:
    if m["role"] == "sistema":
        if m.get("kind") == "feedback":
            with st.chat_message("assistant", avatar="📝"):
                st.markdown(m["content"])
        elif m.get("kind") == "ajuda":
            st.info(m["content"])
        else:
            st.caption(m["content"])
        return

    avatar = AVATARES.get(m.get("mode")) if m["role"] == "assistant" else None
    with st.chat_message(m["role"], avatar=avatar):
        st.markdown(m["content"])
        if m.get("estado"):
            st.caption(f"⚔️ Estado do combate: {m['estado']}")
        if m.get("fontes") or m.get("metricas"):
            with st.expander("📚 Fontes consultadas e métricas"):
                if m.get("fontes"):
                    st.write(f"**Fontes:** {m['fontes']}")
                if m.get("metricas"):
                    st.write(f"**Métricas:** {m['metricas']}")


def exibir_stream(stream, transformar=None):
    """
    Mostra a resposta aos poucos, com um cursor piscando. `transformar` ajusta o texto exibido
    (o Mestre usa para esconder a linha [ESTADO]). Retorna (área, texto completo).
    Se o Ollama falhar no meio, a área é limpa e OllamaError continua subindo.
    """
    ajustar = transformar or (lambda texto: texto)
    area = st.empty()
    try:
        for _ in stream.tokens():
            area.markdown(ajustar(stream.texto) + "▌")
    except OllamaError:
        area.empty()
        raise
    area.markdown(ajustar(stream.texto))
    return area, stream.texto


# ==========================================
# FORMULÁRIOS DE CONFIGURAÇÃO (aparecem quando o usuário entra em Mestre ou Jogador)
# ==========================================
def formulario_mestre() -> None:
    with st.form("form_mestre"):
        st.subheader("🗺️ Nova aventura solo")
        cenario = st.selectbox("Escolha o cenário:", CENARIOS)
        cenario_livre = st.text_input("Ou descreva o seu próprio cenário (opcional):")
        personagem = st.text_input("Sua ficha simplificada (classe, raça e nível):", value=FICHA_MESTRE_PADRAO)
        iniciar = st.form_submit_button("🚀 Iniciar aventura")

    if st.button("← Voltar ao assistente", key="voltar_do_mestre"):
        trocar_modo(MODO_ASSISTENTE)
        st.rerun()

    if iniciar:
        cenario_final = cenario_livre.strip() or cenario
        personagem_final = personagem.strip() or FICHA_GENERICA
        pedido = (f"Quero começar a aventura no cenário '{cenario_final}' com meu personagem "
                  f"'{personagem_final}'. Dê a introdução imersiva e faça a primeira pergunta de ação.")
        try:
            with st.spinner("O Mestre está preparando o mundo e os monstros..."):
                abertura, _, estado = run_master_turn(pedido, cenario_final, personagem_final, [])
        except OllamaError as e:
            st.error(str(e))  # a aventura só começa se o Mestre conseguiu abrir a cena
            return

        st.session_state.mestre_sessao += 1
        st.session_state.mestre_ativo = True
        st.session_state.mestre_cenario = cenario_final
        st.session_state.mestre_personagem = personagem_final
        st.session_state.mestre_estado = estado
        adicionar_aviso(f"🗺️ Nova aventura: **{cenario_final}**, com {personagem_final}.")
        adicionar_mensagem("assistant", abertura, MODO_MESTRE, estado=estado)
        st.rerun()


def formulario_jogador() -> None:
    with st.form("form_jogador"):
        st.subheader("⚔️ Novo personagem controlado pela IA")
        nome = st.text_input("Nome do personagem:", value="Lia")
        descricao = st.text_input("Ficha e personalidade (classe, raça, nível, PV, modificadores e traços):",
                                  value=FICHA_JOGADOR_PADRAO)
        arquetipo = st.selectbox("Perfil de jogador:", ARQUETIPOS_DISPONIVEIS)
        personalizado = st.text_input(
            "Se escolheu 'Personalizado', descreva o perfil (ex.: jogador muito desconfiado e cauteloso):")
        iniciar = st.form_submit_button("🚀 Colocar o jogador na mesa")

    if st.button("← Voltar ao assistente", key="voltar_do_jogador"):
        trocar_modo(MODO_ASSISTENTE)
        st.rerun()

    if iniciar:
        nome = nome.strip() or "Aventureiro"
        st.session_state.jogador_sessao += 1
        st.session_state.jogador_ativo = True
        st.session_state.jogador_nome = nome
        st.session_state.jogador_ficha = f"{nome}. {descricao.strip()}"
        st.session_state.jogador_arquetipo = arquetipo
        st.session_state.jogador_arquetipo_texto = personalizado
        adicionar_aviso(f"⚔️ Novo personagem na mesa: **{nome}** (perfil {arquetipo}).")
        adicionar_mensagem("assistant", saudacao_inicial(nome, arquetipo), MODO_JOGADOR)
        st.rerun()


# ==========================================
# BARRA LATERAL
# ==========================================
def barra_lateral() -> bool:
    """Desenha o menu lateral. Retorna True se o usuário pediu o feedback da sessão (UC09)."""
    pedir_feedback = False
    with st.sidebar:
        st.header("⚙️ Painel de Controle")

        # Se o modo mudou por comando no chat, o seletor precisa acompanhar (antes de ser desenhado)
        if st.session_state.mudou_modo_por_codigo:
            st.session_state.seletor_modo = st.session_state.modo
            st.session_state.mudou_modo_por_codigo = False
        st.session_state.setdefault("seletor_modo", st.session_state.modo)

        escolhido = st.radio(
            "Modo de uso:", MODOS, format_func=lambda m: ROTULOS_MODO[m], key="seletor_modo"
        )
        if escolhido != st.session_state.modo:
            trocar_modo(escolhido)
            st.rerun()

        modo = st.session_state.modo
        st.divider()

        if modo == MODO_MESTRE and st.session_state.mestre_ativo:
            st.caption(f"🏰 {st.session_state.mestre_cenario}\n\n🛡️ {st.session_state.mestre_personagem}")
            if st.button("🔄 Nova aventura", use_container_width=True):
                encerrar_aventura()
                adicionar_aviso("🔄 Aventura encerrada. Configure uma nova para continuar.")
                st.rerun()

        elif modo == MODO_JOGADOR and st.session_state.jogador_ativo:
            st.caption(f"🛡️ {st.session_state.jogador_ficha}")

            # O perfil pode mudar a qualquer momento sem perder o histórico. O valor é copiado para o
            # estado da sessão a cada execução, porque o Streamlit descarta o estado de widgets que
            # deixam de ser exibidos (como ao trocar de modo).
            escolha = st.selectbox(
                "Perfil de jogador:",
                ARQUETIPOS_DISPONIVEIS,
                index=ARQUETIPOS_DISPONIVEIS.index(st.session_state.jogador_arquetipo),
                key="seletor_arquetipo"
            )
            st.session_state.jogador_arquetipo = escolha
            if escolha == "Personalizado":
                st.session_state.jogador_arquetipo_texto = st.text_input(
                    "Descreva o perfil:",
                    value=st.session_state.jogador_arquetipo_texto,
                    key="texto_arquetipo"
                )

            if st.button("📝 Gerar feedback", use_container_width=True):
                pedir_feedback = True
            if st.button("🔄 Novo personagem", use_container_width=True):
                encerrar_personagem()
                adicionar_aviso("🔄 Personagem encerrado. Configure um novo para continuar.")
                st.rerun()

        st.divider()
        if st.button("🗑️ Limpar tudo", use_container_width=True):
            limpar_tudo()
            st.rerun()

        st.caption(f"Modelo local: **{OLLAMA_MODEL}** (Ollama). Funciona sem internet.")
    return pedir_feedback


# ==========================================
# PROCESSAMENTO DAS MENSAGENS
# ==========================================
def processar_feedback() -> bool:
    """UC09: a IA sai do personagem e analisa a condução do Mestre. Retorna True se gerou um aviso/feedback."""
    historico = historico_para_llm(st.session_state.mensagens, MODO_JOGADOR, st.session_state.jogador_sessao)
    if not historico_suficiente(historico):
        adicionar_aviso(AVISO_HISTORICO_CURTO, "ajuda")
        return True
    try:
        with st.spinner("O Mentor está analisando a sua sessão..."):
            texto = gerar_feedback(historico)
    except OllamaError as e:
        st.error(str(e))
        return False
    adicionar_aviso(texto, "feedback")  # fica no chat, mas não vai ao modelo nos próximos turnos
    return True


def processar_mensagem(texto: str) -> None:
    """Envia a fala do usuário ao modo atual e mostra a resposta. Erros do Ollama não entram no histórico."""
    modo = st.session_state.modo
    historico = historico_para_llm(st.session_state.mensagens, modo, sessao_do_modo(modo))

    with st.chat_message("user"):
        st.markdown(texto)

    with st.chat_message("assistant", avatar=AVATARES[modo]):
        extras = {}
        try:
            if modo == MODO_ASSISTENTE:
                with st.spinner("Consultando os tomos sagrados..."):
                    stream, fontes, consulta = run_module1_chat_stream(texto, historico)
                _, resposta = exibir_stream(stream)
                extras = {
                    "fontes": fontes,
                    "metricas": formatar_metricas(stream.prompt_tokens, stream.completion_tokens, consulta, texto),
                }

            elif modo == MODO_MESTRE:
                estado_anterior = st.session_state.mestre_estado
                with st.spinner("O Mestre está consultando as regras..."):
                    stream, fontes = run_master_turn_stream(
                        texto, st.session_state.mestre_cenario, st.session_state.mestre_personagem,
                        historico, estado_anterior
                    )
                area, bruto = exibir_stream(stream, ocultar_linha_estado)
                resposta, novo_estado = extrair_estado(bruto, estado_anterior)
                area.markdown(resposta)
                extras = {"estado": novo_estado, "fontes": fontes}

            else:  # MODO_JOGADOR: respostas curtas, e a checagem do formato [Ação]/[Fala] precisa do texto inteiro
                with st.spinner("O jogador está pensando..."):
                    resposta = run_player_simulator_turn(
                        texto, st.session_state.jogador_ficha, historico,
                        st.session_state.jogador_arquetipo, st.session_state.jogador_arquetipo_texto
                    )
                st.markdown(resposta)
        except OllamaError as e:
            st.error(str(e))
            return

        if not resposta.strip():
            st.warning("O modelo não devolveu texto. Tente de novo.")
            return

        if modo == MODO_MESTRE:
            if extras["estado"]:
                st.caption(f"⚔️ Estado do combate: {extras['estado']}")
            if extras["fontes"] and extras["fontes"] != "N/A":
                with st.expander("📚 Fontes consultadas e métricas"):
                    st.write(f"**Fontes:** {extras['fontes']}")
        elif modo == MODO_ASSISTENTE:
            with st.expander("📚 Fontes consultadas e métricas"):
                st.write(f"**Fontes:** {extras['fontes']}")
                st.write(f"**Métricas:** {extras['metricas']}")

    if modo == MODO_MESTRE:
        st.session_state.mestre_estado = extras["estado"]
    adicionar_mensagem("user", texto, modo)
    adicionar_mensagem("assistant", resposta, modo, **extras)


# ==========================================
# EXECUÇÃO DA PÁGINA
# ==========================================
iniciar_estado()
garantir_ollama()

# A entrada é lida primeiro: um comando pode trocar o modo antes de o resto da página ser desenhada.
entrada = st.chat_input(
    PLACEHOLDER_CONFIGURAR if precisa_configurar() else PLACEHOLDERS[st.session_state.modo]
)

pedir_feedback = False
if entrada:
    acao = interpretar_entrada(entrada, st.session_state.modo)
    if acao.tipo == "trocar_modo":
        if acao.modo == st.session_state.modo:
            adicionar_aviso(f"Você já está no modo {ROTULOS_MODO[acao.modo]}.")
        else:
            trocar_modo(acao.modo)
        st.rerun()
    elif acao.tipo == "ajuda":
        adicionar_aviso(AJUDA, "ajuda")
        st.rerun()
    elif acao.tipo == "feedback":
        if st.session_state.modo == MODO_JOGADOR and st.session_state.jogador_ativo:
            pedir_feedback = True
            entrada = None
        else:
            adicionar_aviso("O feedback só está disponível no modo Jogador, com um personagem em jogo.", "ajuda")
            st.rerun()

pedir_feedback = barra_lateral() or pedir_feedback
if pedir_feedback and processar_feedback():
    st.rerun()

st.title("🎲 RPG Tabletop AI Assistant")
st.caption(DESCRICOES[st.session_state.modo])

for mensagem in st.session_state.mensagens:
    exibir_mensagem(mensagem)

if precisa_configurar():
    if entrada:  # os comandos já foram tratados acima; uma fala comum ainda não tem para quem ir
        st.warning("Configure a sessão abaixo antes de conversar (ou use /assistente para voltar).")
    if st.session_state.modo == MODO_MESTRE:
        formulario_mestre()
    else:
        formulario_jogador()
elif entrada:
    processar_mensagem(entrada)