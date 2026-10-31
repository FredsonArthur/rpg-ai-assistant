"""
Calibração da barreira "só os livros"
-------------------------------------
Roda perguntas de dentro e de fora do tema na sua base de livros, mostra a similaridade do melhor
trecho de cada uma e sugere o limiar (relevancia_minima) que melhor separa os dois grupos.

Uso:
    python -m rpgassistant.calibrar
    python -m rpgassistant.calibrar --dentro minhas_perguntas.txt --fora fora_do_tema.txt

Os arquivos têm uma pergunta por linha. Para aplicar o resultado:
    RPG_RELEVANCIA_MINIMA=0.35 python main.py        (ou altere o padrão em rpgassistant/config.py)
"""

from __future__ import annotations

import argparse
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Sequence

from rpgassistant import config
from rpgassistant.errors import BaseVaziaError
from rpgassistant.logs import configurar_logs
from rpgassistant.services import rag

PERGUNTAS_DENTRO = [
    "Como funciona a condição Agarrado?",
    "Quanto tempo dura um descanso longo?",
    "O que é vantagem em um teste?",
    "Como funciona a ação de Esquivar?",
    "Quais são as escolas de magia?",
    "Como funciona o ataque de oportunidade?",
    "O que é uma salvaguarda contra morte?",
    "Qual o dano de uma queda?",
    "Como funciona a iniciativa?",
    "O que faz um Bárbaro?",
    "Quais raças posso escolher para o meu personagem?",
    "Como funciona a concentração em magias?",
    "O que é a Classe de Armadura?",
    "Como funciona a furtividade?",
    "Crie um NPC estalajadeiro com um segredo.",
]
PERGUNTAS_FORA = [
    "O que é uma rede neural?",
    "Qual a capital da França?",
    "Como fazer um bolo de chocolate?",
    "Quem ganhou a Copa do Mundo de 2014?",
    "Como instalar o Python no Windows?",
    "Explique a teoria da relatividade.",
    "Receita de feijoada.",
    "Como funciona o imposto de renda?",
    "Quem foi Napoleão Bonaparte?",
    "Como treinar para uma maratona?",
    "O que é blockchain?",
    "Qual a melhor linguagem de programação para iniciantes?",
]


@dataclass(frozen=True)
class Sugestao:
    limiar: float
    acertos: int
    total: int
    separavel: bool             # True se nenhuma pergunta de dentro ficou abaixo de uma de fora
    minimo_dentro: float
    maximo_fora: float


def sugerir_limiar(dentro: Sequence[float], fora: Sequence[float]) -> Sugestao:
    """
    Escolhe o limiar que acerta mais perguntas: as de dentro precisam ficar no limiar ou acima dele
    (respondidas) e as de fora abaixo (recusadas). Havendo vários limiares empatados, usa o do meio.
    """
    if not dentro or not fora:
        raise ValueError("Preciso de pelo menos uma pergunta de dentro e uma de fora do tema.")

    def acertos(limiar: float) -> int:
        return sum(s >= limiar for s in dentro) + sum(s < limiar for s in fora)

    candidatos = [i / 100 for i in range(0, 101)]
    melhor = max(acertos(t) for t in candidatos)
    empatados = [t for t in candidatos if acertos(t) == melhor]
    limiar = round(statistics.median(empatados), 2)
    return Sugestao(limiar, melhor, len(dentro) + len(fora), min(dentro) > max(fora), min(dentro), max(fora))


def ler_perguntas(caminho: Path) -> List[str]:
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    return [linha.strip() for linha in linhas if linha.strip() and not linha.strip().startswith("#")]


def _similaridades(perguntas: Sequence[str], buscar: Callable) -> List[float]:
    minimo = config.settings.relevancia_minima
    valores = []
    for pergunta in perguntas:
        melhor = buscar(pergunta).melhor_similaridade
        valor = melhor if melhor is not None else 0.0
        valores.append(valor)
        print(f"  {valor:5.2f}  {'passa ' if valor >= minimo else 'recusa'}  {pergunta}")
    return valores


def calibrar(dentro: Sequence[str], fora: Sequence[str], buscar: Callable = rag.buscar_contexto) -> Sugestao:
    print(f"Limiar atual: {config.settings.relevancia_minima:.2f}\n")
    print("Perguntas DENTRO do tema (deveriam passar):")
    sim_dentro = _similaridades(dentro, buscar)
    print("\nPerguntas FORA do tema (deveriam ser recusadas):")
    sim_fora = _similaridades(fora, buscar)

    sugestao = sugerir_limiar(sim_dentro, sim_fora)
    print(f"\nMenor similaridade entre as de dentro: {sugestao.minimo_dentro:.2f}")
    print(f"Maior similaridade entre as de fora:   {sugestao.maximo_fora:.2f}")
    if sugestao.separavel:
        print("Os dois grupos se separam bem.")
    else:
        print("Atenção: há perguntas de dentro com similaridade menor que alguma de fora. Nenhum limiar acerta tudo;")
        print("o sugerido é o que erra menos. Vale revisar as perguntas ou o tamanho dos trechos (CHUNK_SIZE).")
    print(f"\nLimiar sugerido: {sugestao.limiar:.2f}  (acerta {sugestao.acertos} de {sugestao.total})")
    print(f"Para aplicar:  RPG_RELEVANCIA_MINIMA={sugestao.limiar:.2f} python main.py")
    return sugestao


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Calibra o limiar de relevância do Assistente.")
    parser.add_argument("--dentro", type=Path, help="arquivo com perguntas de RPG (uma por linha)")
    parser.add_argument("--fora", type=Path, help="arquivo com perguntas fora do tema (uma por linha)")
    args = parser.parse_args(argv)

    configurar_logs()
    dentro = ler_perguntas(args.dentro) if args.dentro else PERGUNTAS_DENTRO
    fora = ler_perguntas(args.fora) if args.fora else PERGUNTAS_FORA
    try:
        calibrar(dentro, fora)
    except BaseVaziaError as e:
        print(e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())