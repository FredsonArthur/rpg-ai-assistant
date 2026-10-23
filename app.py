"""
Interface Gráfica Principal (Streamlit)
---------------------------------------
Fornece uma interface de chat unificada para interagir com o assistente RAG de D&D 5e,
permitindo tirar dúvidas de regras, consultar lore e gerar conteúdo para o Mestre.
"""

import streamlit as st
from src.rag_engine import query_rag
from src.prompt_templates import SYSTEM_PROMPT

# Configuração da página
st.set_page_config(
    page_title="Assistente D&D 5e",
    page_icon="🎲",
    layout="wide"
)

# Barra lateral para controlos e informações
with st.sidebar:
    st.header("⚙️ Painel de Controlo")
    
    # Botão para limpar o histórico do chat
    if st.button("🗑️ Limpar Conversa", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
        
    st.divider()
    st.markdown("### 📚 Sobre o Assistente")
    st.markdown(
        "Este assistente utiliza um motor **RAG unificado** "
        "ligado aos manuais Core (2024/2025) e suplementos oficiais de D&D 5e."
    )
    st.caption("Desenvolvido para campanhas e sessões de RPG.")

# Cabeçalho principal
st.title("🎲 Assistente Pessoal de D&D 5e (2024/2025)")
st.caption("Pergunte sobre regras, lore dos livros ou peça para gerar encontros, NPCs e ideias de campanha numa única conversa.")

# Inicializa o histórico de chat no estado da sessão
if "messages" not in st.session_state:
    st.session_state.messages = []

# Exibe o histórico de mensagens anteriores
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Campo de entrada de texto do utilizador
if user_input := st.chat_input("Ex: Como funciona o Descanso Curto? Ou crie um NPC cultista Nível 2."):
    # Adiciona a pergunta do utilizador ao histórico e exibe-a
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Executa a consulta ao motor RAG e gera a resposta via Ollama
    with st.chat_message("assistant"):
        with st.spinner("A consultar os tomos sagrados..."):
            response_text, sources, metrics = query_rag(
                user_input, 
                prompt_template=SYSTEM_PROMPT
            )
            st.markdown(response_text)
            
            # Exibe as fontes bibliográficas e métricas de tokens num painel expansível
            with st.expander("📚 Fontes consultadas e Métricas"):
                st.write(f"**Fontes:** {sources}")
                st.write(f"**Métricas:** {metrics}")

    # Salva a resposta do assistente no histórico
    st.session_state.messages.append({"role": "assistant", "content": response_text})