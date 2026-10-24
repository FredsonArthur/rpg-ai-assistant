"""
Módulo 2: Simulador IA Mestre de Treino (UC04, UC05, UC06)
----------------------------------------------------------
Simula um Dungeon Master (DM) experiente que conduz uma aventura solo (One-on-One),
processa as ações do jogador, solicita testes de dados (baseados no RAG) e gerencia combates.
"""

import ollama
from typing import Tuple
from src.config import OLLAMA_MODEL
from src.rag_engine import recuperar_contexto

MASTER_SYSTEM_PROMPT = """Você é um Mestre de RPG (Dungeon Master) experiente, narrativo, justo e didático em D&D 5e.
Você está conduzindo uma sessão de aventura solo (One-on-One) com o seguinte jogador:

[DADOS DA SESSÃO]
- Cenário: {scenario}
- Personagem do Jogador: {character}

DIRETRIZES DE COMPORTAMENTO OBRIGATÓRIAS:
1. IDIOMA: Responda SEMPRE em Português do Brasil.
2. NARRATIVA IMERSIVA: Descreva o ambiente, os NPCs e as reações do mundo focando em visão, som e atmosfera.
3. AUTONOMIA DO JOGADOR: NUNCA tome decisões, fale ou execute ações pelo personagem do jogador. Apenas reaja ao que ele fizer.
4. TESTES DE DADOS E MECÂNICA: 
   - Se a ação do jogador envolver risco, investigação, perícia ou combate, exija explicitamente uma rolagem de teste informando o atributo e a Classe de Dificuldade (Ex: "Faça um teste de Destreza (Acrobacia) CD 13").
   - Aguarde o jogador informar o resultado do dado para narrar o sucesso ou a falha.
   - Para ações simples e sem risco, narre o sucesso diretamente sem pedir dados.
5. COMBATE E ESTATÍSTICAS: Gerencie turnos de forma clara, descrevendo o impacto dos ataques e controlando os oponentes de acordo com as regras oficiais de D&D 5e.

Contexto dos Manuais de Regras e Monstros:
{context}

Resposta do Mestre Virtual:"""


def run_master_turn(user_input: str, scenario: str, character: str, chat_history: list) -> Tuple[str, str]:
    """
    Processa um turno do Módulo 2 (Mestre Virtual), consultando o contexto relevante (se necessário)
    e gerando a resposta narrativa via Ollama mantendo o histórico da sessão.
    """
    # 1. Recupera contexto relevante do RAG com base na ação do usuário (ex: monstros, armadilhas, regras)
    contexto, fontes = recuperar_contexto(user_input, k=3)

    # 2. Formata o prompt do sistema com os dados da sessão e o contexto recuperado
    system_prompt = MASTER_SYSTEM_PROMPT.format(
        scenario=scenario,
        character=character,
        context=contexto
    )

    # 3. Monta as mensagens para o Ollama (System Prompt + Histórico de Mensagens + Nova Entrada)
    messages = [{"role": "system", "content": system_prompt}]
    
    for msg in chat_history[-10:]:  # Mantém as últimas 10 mensagens para contexto eficiente
        messages.append({"role": msg["role"], "content": msg["content"]})
        
    messages.append({"role": "user", "content": user_input})

    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=messages
        )
        resposta_llm = response['message']['content']
        return resposta_llm, fontes
    except Exception as e:
        error_msg = f"Erro ao comunicar com o Mestre Virtual (Ollama): {e}. Verifique se o 'ollama serve' está ativo."
        return error_msg, "N/A"