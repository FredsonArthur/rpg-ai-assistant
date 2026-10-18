import streamlit as st
from src.rag_engine import consultar_rag  # Módulo de backend do RAG

st.set_page_config(page_title="Assistente de RPG - RAG", page_icon="🎲", layout="wide")

st.title("🎲 Assistente Inteligente para Mestres e Jogadores de RPG")
st.sidebar.header("Módulos de Operação")

# Seleção do Caso de Uso (Módulo 1)
uc_selecionado = st.sidebar.selectbox(
    "Escolha a Funcionalidade:",
    [
        "UC01: Consultar Regra ou Mecânica",
        "UC02: Consultar Lore e Ambientação",
        "UC03: Gerar Conteúdo Auxiliar (Mestre)"
    ]
)

st.sidebar.markdown("---")
st.sidebar.info("Certifique-se de que a base vetorial está populada em `data/vectordb/` antes de realizar as consultas.")

# --- UC01: Consultar Regra ou Mecânica ---
if uc_selecionado == "UC01: Consultar Regra ou Mecânica":
    st.header("📖 Consulta de Regras e Mecânicas")
    st.write("Faça perguntas sobre magias, condições, testes de resistência ou regras de combate.")
    
    pergunta_usuario = st.text_input("Ex: Como funciona a ação de Agarrar ou o Descanso Longo?")
    
    if st.button("Consultar Regra"):
        if pergunta_usuario:
            with st.spinner("Buscando nos manuais oficiais..."):
                # Executa o pipeline de RAG focando em regras (UC01)
                resposta, fontes, metricas = consultar_rag(pergunta_usuario, tipo="regras")
                
                st.subheader("Resposta:")
                st.write(resposta)
                
                st.markdown("---")
                st.caption(f"📚 **Fonte:** {fontes}")
                st.caption(f"⚡ **Métricas:** {metricas}")
        else:
                    st.warning("Por favor, digite uma pergunta.")

# --- UC02: Consultar Lore e Ambientação ---
elif uc_selecionado == "UC02: Consultar Lore e Ambientação":
    st.header("🗺️ Consulta de Lore e Panteão")
    st.write("Consulte a história de cidades, deuses, geografia e background de universos de RPG.")
    
    pergunta_lore = st.text_input("Ex: Quem é Tiamat e qual a sua relação com os dragões cromáticos?")
    
    if st.button("Investigar nos Tomos"):
        if pergunta_lore:
            with st.spinner("Consultando arquivos de ambientação..."):
                resposta, fontes, metricas = consultar_rag(pergunta_lore, tipo="lore")
                
                st.subheader("Registro Histórico:")
                st.write(resposta)
                
                st.markdown("---")
                st.caption(f"📜 **Fonte:** {fontes}")
                st.caption(f"⚡ **Métricas:** {metricas}")
        else:
            st.warning("Por favor, digite sua dúvida sobre a história do mundo.")

# --- UC03: Gerar Conteúdo Auxiliar para Mestre ---
elif uc_selecionado == "UC03: Gerar Conteúdo Auxiliar para Mestre":
    st.header("🛠️ Criador de Conteúdo Original para Mestres")
    st.write("Crie NPCs, itens mágicos ou ganchos de aventura balanceados para o nível do seu grupo.")
    
    pedido_mestre = st.text_area("Descreva o que deseja criar:", 
                                placeholder="Ex: Preciso de um NPC ferreiro elfo corrompido por magia sombria, adequado para um grupo de Nível 4.")
    
    if st.button("Gerar Conteúdo com IA"):
        if pedido_mestre:
            with st.spinner("Analisando diretrizes de balanceamento e gerando conteúdo..."):
                resposta, fontes, metricas = consultar_rag(pedido_mestre, tipo="criacao")
                
                st.subheader("Conteúdo Gerado:")
                st.write(resposta)
                
                st.markdown("---")
                st.caption(f"⚖️ **Parâmetros Baseados em:** {fontes}")
                st.caption(f"⚡ **Métricas:** {metricas}")
        else:
            st.warning("Por favor, descreva o elemento que deseja criar.")