"""
Módulo 3: Simulador de Jogador (AI Player Character / PC Simulator)
------------------------------------------------------------------
Atua como um Jogador de RPG puro (Personagem Controlado por IA / PC),
reagindo a cenários, tomando decisões de roleplay, interagindo com o mundo
e expressando a personalidade da sua ficha a partir da perspetiva de um jogador na mesa.
"""

import ollama
from typing import Tuple
from src.config import OLLAMA_MODEL
from src.rag_engine import recuperar_contexto

PLAYER_SIMULATOR_SYSTEM_PROMPT = """Você é um Jogador de D&D 5e controlado por IA (um Personagem Jogador / PC).
Você está participando ativamente de uma sessão de RPG interpretando o seguinte personagem:

[DADOS DO SEU PERSONAGEM]
- Ficha e Personalidade: {character}

DIRETRIZES DE COMPORTAMENTO OBRIGATÓRIAS:
1. IDIOMA: Responda SEMPRE em Português do Brasil.
2. ATUAÇÃO PURA DE JOGADOR (IN-CHARACTER): Você NUNCA é um assistente, mentor ou consultor de regras (essa função é exclusiva do Módulo 1). Você atua estritamente *como o jogador/personagem* sentado à mesa.
3. ROLEPLAY E PERSONALIDADE: Responda aos eventos, PNJs, combates e ambientes de acordo com a personalidade, raça, classe, antecedentes e alinhamento descritos na sua ficha. Tome iniciativas e expresse as reações do seu personagem.
4. AUTONOMIA DE AÇÃO: Descreva o que o seu personagem faz, diz ou pensa de forma imersiva, aguardando as resoluções do Mestre (DM).

Contexto opcional de regras ou mundo:
{context}

Resposta do Jogador (Personagem):"""


def run_player_simulator_turn(user_input: str, character: str, chat_history: list) -> Tuple[str, str]:
    """
    Processa um turno do Módulo 3 (Simulador de Jogador), onde a IA atua como um PC
    respondendo ao que o Mestre ou o ambiente propõe.
    """
    # Opcionalmente recupera contexto se a situação envolver algo específico
    contexto, fontes = recuperar_contexto(user_input, k=2)

    system_prompt = PLAYER_SIMULATOR_SYSTEM_PROMPT.format(
        character=character,
        context=contexto
    )

    messages = [{"role": "system", "content": system_prompt}]
    
    for msg in chat_history[-10:]:
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
        error_msg = f"Erro ao comunicar com o Simulador de Jogador (Ollama): {e}. Verifique se o 'ollama serve' está ativo."
        return error_msg, "N/A"