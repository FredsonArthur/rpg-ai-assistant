"""
Interface Gráfica Principal (Streamlit) - RPG Tabletop AI Assistant
-------------------------------------------------------------------
Este script gere a interface gráfica central da aplicação construída em Streamlit.
Funcionalidades principais:
1. Verificação automática e arranque em segundo plano do servidor Ollama.
2. Navegação lateral baseada em arquitetura modular (Módulo 1, Módulo 2 e Módulo 3).
3. Gestão de estados de sessão para histórico de chat de cada módulo.
4. Interface interativa para o Módulo 1 (Tutor), Módulo 2 (Mestre) e Módulo 3 (Jogador IA).
"""

import socket
import subprocess
import streamlit as st
from src.modules.module1_tutor import run_module1_chat
from src.modules.module2_master import run_master_turn
from src.modules.module3_player import run_player_simulator_turn


def ensure_ollama_is_running() -> None:
    """
    Verifica se o serviço do Ollama está ativo na porta local padrão (11434).
    Caso não esteja a responder, inicia o comando 'ollama serve' automaticamente
    em segundo plano para evitar falhas de comunicação com a LLM local.
    """
    host = "127.0.0.1"
    port = 11434
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        result = s.connect_ex((host, port))
        if result != 0:  # Porta fechada / Serviço inativo
            try:
                subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
            except Exception as e:
                print(f"Aviso: Não foi possível iniciar o Ollama automaticamente: {e}")


# Executa a verificação do Ollama antes de renderizar a página
ensure_ollama_is_running()

# Configuração global da página do Streamlit
st.set_page_config(
    page_title="RPG Tabletop AI Assistant",
    page_icon="🎲",
    layout="wide"
)

# Inicializa o estado global de mensagens do Módulo 1 se não existir
if "messages" not in st.session_state:
    st.session_state.messages = []

# ==========================================
# BARRA LATERAL (SIDEBAR) & CONTROLOS
# ==========================================
with st.sidebar:
    st.header("⚙️ Painel de Controlo")
    
    selected_module = st.selectbox(
        "Selecione o Módulo:",
        [
            "Módulo 1: Tutor & Consultor (RAG)",
            "Módulo 2: Simulador Mestre (DM)",
            "Módulo 3: Simulador Jogador (AI PC)"
        ]
    )
    
    st.divider()
    
    if st.button("🗑️ Limpar Conversa", use_container_width=True):
        if "Módulo 1" in selected_module:
            st.session_state.messages = []
        elif "Módulo 2" in selected_module:
            st.session_state.module2_messages = []
            st.session_state.module2_active = False
        elif "Módulo 3" in selected_module:
            st.session_state.module3_messages = []
            st.session_state.module3_active = False
        st.rerun()
        
    st.divider()
    st.markdown("### 📚 Sobre o Assistente")
    st.markdown(
        "Arquitetura modular baseada em IA local (**Ollama / Llama 3**) "
        "e busca semântica vetorial em manuais oficiais de D&D 5e (2024/2025)."
    )
    st.caption("Desenvolvido para campanhas e sessões de RPG de mesa.")


# ==========================================
# ROTEAMENTO DE MÓDULOS (INTERFACE)
# ==========================================

# ------------------------------------------
# MÓDULO 1: Tutor, Regras e Lore (RAG)
# ------------------------------------------
if "Módulo 1" in selected_module:
    st.title("🎲 Módulo 1: Tutor de Regras, Lore & Geração")
    st.caption("Consulte regras das edições 2024/2025, explore a lore dos suplementos ou crie NPCs, encontros e itens.")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if user_input := st.chat_input("Ex: Como funciona a condição Amedrontado [Frightened]? Ou crie um NPC estalajadeiro."):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("A consultar os tomos sagrados..."):
                response_text, sources, metrics = run_module1_chat(user_input)
                st.markdown(response_text)
                
                with st.expander("📚 Fontes consultadas e Métricas"):
                    st.write(f"**Fontes:** {sources}")
                    st.write(f"**Métricas:** {metrics}")

        st.session_state.messages.append({"role": "assistant", "content": response_text})

# ------------------------------------------
# MÓDULO 2: Simulador Mestre (Dungeon Master)
# ------------------------------------------
elif "Módulo 2" in selected_module:
    st.title("🗺️ Módulo 2: Simulador Mestre (Dungeon Master)")
    st.caption("A IA assume o papel de Mestre de Jogo (DM) em uma aventura solo (One-on-One), guiando sua exploração, solicitando testes e gerindo combates.")

    if "module2_messages" not in st.session_state:
        st.session_state.module2_messages = []
    if "module2_active" not in st.session_state:
        st.session_state.module2_active = False

    if not st.session_state.module2_active:
        st.subheader("⚙️ Configuração da Sessão de Aventura Solo")
        with st.form("setup_adventure_form"):
            scenario_choice = st.selectbox(
                "Escolha o Cenário / Tipo de Aventura:",
                [
                    "Masmorra nas Ruínas de uma Tumba Antiga",
                    "Investigação Urbana em uma Taverna Assombrada",
                    "Floresta Sombria e Pântano dos Goblins",
                    "Covil do Dragão Jovem nas Montanhas Geladas"
                ]
            )
            character_choice = st.text_input(
                "Defina sua Ficha Simplificada (Classe, Raça e Nível):",
                value="Guerreiro Humano, Nível 2 (Espada Curta, Escudo, Cota de Malha)"
            )
            
            submitted = st.form_submit_button("🚀 Iniciar Aventura Solo")
            if submitted:
                st.session_state.module2_scenario = scenario_choice
                st.session_state.module2_character = character_choice
                st.session_state.module2_active = True
                
                initial_prompt = f"Quero começar a aventura no cenário '{scenario_choice}' com meu personagem '{character_choice}'. Dê a introdução imersiva e faça a primeira pergunta de ação."
                
                with st.spinner("O Mestre Virtual está a preparar o mundo e os monstros..."):
                    opening_response, _ = run_master_turn(
                        initial_prompt, 
                        scenario_choice, 
                        character_choice, 
                        []
                    )
                
                st.session_state.module2_messages = [
                    {"role": "assistant", "content": opening_response}
                ]
                st.rerun()
    else:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.info(f"🏰 **Cenário:** {st.session_state.module2_scenario} | 🛡️ **Personagem:** {st.session_state.module2_character}")
        with col2:
            if st.button("🔄 Reiniciar Aventura", use_container_width=True):
                st.session_state.module2_active = False
                st.session_state.module2_messages = []
                st.rerun()

        st.divider()

        for message in st.session_state.module2_messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if player_action := st.chat_input("Descreva sua ação (Ex: 'Olho ao redor', 'Ataco o esqueleto com minha espada', 'Tirei 16 no dado'):"):
            st.session_state.module2_messages.append({"role": "user", "content": player_action})
            with st.chat_message("user"):
                st.markdown(player_action)

            with st.chat_message("assistant"):
                with st.spinner("O Mestre está a julgar a sua acção e a consultar as regras..."):
                    dm_response, sources = run_master_turn(
                        player_action,
                        st.session_state.module2_scenario,
                        st.session_state.module2_character,
                        st.session_state.module2_messages
                    )
                    st.markdown(dm_response)
                    
                    if sources and sources != "N/A":
                        with st.expander("📚 Regras/Fontes consultadas pelo Mestre"):
                            st.write(f"**Fontes:** {sources}")

            st.session_state.module2_messages.append({"role": "assistant", "content": dm_response})

# ------------------------------------------
# MÓDULO 3: Simulador Jogador (AI PC)
# ------------------------------------------
elif "Módulo 3" in selected_module:
    st.title("⚔️ Módulo 3: Simulador Jogador (AI PC)")
    st.caption("A IA assume o papel de um Jogador Puro (Personagem Jogador), reagindo aos seus cenários, interpretando a ficha e tomando decisões na mesa.")

    if "module3_messages" not in st.session_state:
        st.session_state.module3_messages = []
    if "module3_active" not in st.session_state:
        st.session_state.module3_active = False

    # Tela de Configuração do Personagem Jogador da IA
    if not st.session_state.module3_active:
        st.subheader("🛡️ Configuração do Personagem Controlado por IA")
        with st.form("setup_player_simulator_form"):
            ai_character_profile = st.text_input(
                "Defina a Ficha e a Personalidade do Jogador IA:",
                value="Ladino Tiefling (Trapaceiro Arcano), Nível 3, desconfiado, curioso e focado em furtividade."
            )
            
            submitted_ai_player = st.form_submit_button("🚀 Iniciar Jogador IA na Mesa")
            if submitted_ai_player:
                st.session_state.module3_character = ai_character_profile
                st.session_state.module3_active = True
                
                # O Jogador IA apresenta-se ou assume a posição na mesa
                st.session_state.module3_messages = [
                    {"role": "assistant", "content": f"*{ai_character_profile.split(',')[0]} acena com a cabeça, ajeita o seu equipamento e aguarda as ordens ou o início dos acontecimentos.* 'Estou pronto. O que fazemos agora?'"}
                ]
                st.rerun()
    else:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.info(f"🛡️ **Jogador IA Ativo:** {st.session_state.module3_character}")
        with col2:
            if st.button("🔄 Alterar Personagem", use_container_width=True):
                st.session_state.module3_active = False
                st.session_state.module3_messages = []
                st.rerun()

        st.divider()

        for message in st.session_state.module3_messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if dm_prompt := st.chat_input("Dê uma situação ou fala para o Jogador IA (Ex: 'Vocês entram numa sala escura cheia de teias', 'O estalajadeiro pergunta o que querem beber'):"):
            st.session_state.module3_messages.append({"role": "user", "content": dm_prompt})
            with st.chat_message("user"):
                st.markdown(dm_prompt)

            with st.chat_message("assistant"):
                with st.spinner("O Jogador IA está a pensar e a decidir a sua ação..."):
                    ai_player_response, sources = run_player_simulator_turn(
                        dm_prompt,
                        st.session_state.module3_character,
                        st.session_state.module3_messages
                    )
                    st.markdown(ai_player_response)
                    
                    if sources and sources != "N/A":
                        with st.expander("📚 Consulta de apoio"):
                            st.write(f"**Fontes:** {sources}")

            st.session_state.module3_messages.append({"role": "assistant", "content": ai_player_response})