"""
Calibração da barreira "só os livros"
-------------------------------------
Roda perguntas de dentro e de fora do tema na sua base de livros, mostra a similaridade do melhor
trecho de cada uma e sugere o limiar (relevancia_minima) que melhor separa os dois grupos.

Uso:
    python -m rpgassistant.calibrar
    python -m rpgassistant.calibrar --dentro minhas_perguntas.txt --fora fora_do_tema.txt

Os arquivos têm uma pergunta por linha (linhas vazias e as que começam com # são ignoradas).

Para aplicar o resultado, defina RPG_RELEVANCIA_MINIMA ao abrir o app. O script mostra, no final, o
comando certo para cada terminal (Linux/macOS, PowerShell e Prompt de Comando). Também é possível
alterar o padrão `relevancia_minima` em rpgassistant/config.py.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

from rpgassistant import config
from rpgassistant.errors import BaseVaziaError
from rpgassistant.logs import configurar_logs
from rpgassistant.services import rag

# Perguntas que os livros cobrem: a similaridade delas deveria ficar ACIMA do limiar (passam).
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
# Perguntas sem relação com RPG: a similaridade delas deveria ficar ABAIXO do limiar (são recusadas).
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
    """O limiar sugerido e os números que o justificam."""

    limiar: float
    acertos: int                # quantas perguntas esse limiar classifica certo
    total: int                  # quantas perguntas foram testadas ao todo
    separavel: bool             # True se nenhuma pergunta de dentro ficou abaixo de uma de fora
    minimo_dentro: float        # a pior similaridade entre as perguntas de dentro
    maximo_fora: float          # a melhor similaridade entre as perguntas de fora


def sugerir_limiar(dentro: Sequence[float], fora: Sequence[float]) -> Sugestao:
    """
    Escolhe o limiar que acerta mais perguntas: as de dentro precisam ficar no limiar ou acima dele
    (respondidas) e as de fora abaixo (recusadas). Havendo vários limiares empatados, usa o do meio.
    """
    if not dentro or not fora:
        raise ValueError("Preciso de pelo menos uma pergunta de dentro e uma de fora do tema.")

    def acertos(limiar: float) -> int:
        return sum(s >= limiar for s in dentro) + sum(s < limiar for s in fora)

    # Testa todos os limiares de 0.00 a 1.00, de centésimo em centésimo.
    candidatos = [i / 100 for i in range(0, 101)]
    melhor = max(acertos(t) for t in candidatos)
    empatados = [t for t in candidatos if acertos(t) == melhor]
    limiar = round(statistics.median(empatados), 2)
    return Sugestao(limiar, melhor, len(dentro) + len(fora), min(dentro) > max(fora), min(dentro), max(fora))


def ler_perguntas(caminho: Path) -> List[str]:
    """Lê um arquivo com uma pergunta por linha, ignorando linhas vazias e comentários (#)."""
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    return [linha.strip() for linha in linhas if linha.strip() and not linha.strip().startswith("#")]


def comandos_para_aplicar(limiar: float) -> List[Tuple[str, str]]:
    """
    Comandos que abrem o app com `RPG_RELEVANCIA_MINIMA` definida, um para cada terminal.
    Devolve uma lista de (nome do terminal, comando). A sintaxe muda de terminal para terminal:
    - Linux/macOS: a variável vem antes do comando e vale só para essa execução.
    - PowerShell: a variável é definida em `$env:` e vale até fechar o terminal.
    - Prompt de Comando (cmd): `set` com aspas, porque sem elas o espaço antes do `&&` entraria no valor.
    """
    valor = f"{limiar:.2f}"
    return [
        ("Linux/macOS", f"RPG_RELEVANCIA_MINIMA={valor} python main.py"),
        ("Windows (PowerShell)", f'$env:RPG_RELEVANCIA_MINIMA = "{valor}"; python main.py'),
        ("Windows (cmd)", f'set "RPG_RELEVANCIA_MINIMA={valor}" && python main.py'),
    ]


def _similaridades(perguntas: Sequence[str], buscar: Callable) -> List[float]:
    """Busca cada pergunta nos livros, imprime o resultado e devolve a similaridade do melhor trecho de cada uma."""
    minimo = config.settings.relevancia_minima
    valores = []
    for pergunta in perguntas:
        melhor = buscar(pergunta).melhor_similaridade
        valor = melhor if melhor is not None else 0.0  # nenhum trecho encontrado conta como zero
        valores.append(valor)
        print(f"  {valor:5.2f}  {'passa ' if valor >= minimo else 'recusa'}  {pergunta}")
    return valores


def calibrar(dentro: Sequence[str], fora: Sequence[str], buscar: Callable = rag.buscar_contexto) -> Sugestao:
    """
    Roda os dois grupos de perguntas, imprime o relatório e devolve a sugestão de limiar.
    `buscar` pode ser trocada nos testes por uma busca falsa.
    """
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
        print("o sugerido é o que erra menos. Vale revisar as perguntas ou o tamanho dos trechos (chunk_size em config.py).")
    print(f"\nLimiar sugerido: {sugestao.limiar:.2f}  (acerta {sugestao.acertos} de {sugestao.total})")
    print("Para aplicar, use o comando do seu terminal:")
    for terminal, comando in comandos_para_aplicar(sugestao.limiar):
        print(f"  {terminal:<21} {comando}")
    return sugestao


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Ponto de entrada de `python -m rpgassistant.calibrar`. Devolve 0 se deu certo e 1 se a base não existe."""
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
        # Sem livros indexados não há o que calibrar; a mensagem do erro já diz o comando para indexar.
        print(e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())