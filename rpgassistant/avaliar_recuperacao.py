"""
Avaliação da busca nos livros
-----------------------------
Mede se a busca encontra, nos SEUS livros, o trecho que responde a cada pergunta de uma lista. Serve para
saber se o tamanho dos trechos (chunk_size) e o resto da configuração da busca funcionam bem, e para
descobrir as perguntas que a busca erra.

Como funciona: para cada pergunta, a busca traz os `k` trechos mais parecidos. Um trecho "acerta" se
contiver pelo menos um dos termos esperados (sem diferenciar maiúsculas, acentos nem quebras de linha, e
só como palavra inteira) e, se a pergunta indicar um livro, se vier desse livro. O relatório mostra em que
posição o primeiro acerto apareceu (1 é o melhor) e resume os números.

Uso:
    python -m rpgassistant.avaliar_recuperacao
    python -m rpgassistant.avaliar_recuperacao --perguntas minhas_perguntas.txt --k 5

Sem --perguntas, usa PERGUNTAS_DE_EXEMPLO, escritas pensando em livros de D&D 5e em inglês, com alternativas
em português. Elas são só um ponto de partida: os termos precisam existir nos seus livros. Para usar as
suas, crie um arquivo de texto com uma pergunta por linha (linhas vazias e as que começam com # são
ignoradas), neste formato:

    pergunta | termo 1 ; termo 2 ; termo 3 | livro (opcional)

Exemplo:
    Quanto tempo dura um descanso longo? | at least 8 hours ; pelo menos 8 horas | Player's Handbook
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

from rpgassistant import config
from rpgassistant.core.modos import normalizar
from rpgassistant.errors import BaseVaziaError
from rpgassistant.logs import configurar_logs
from rpgassistant.services import rag
from rpgassistant.services.rag import Trecho


@dataclass(frozen=True)
class Pergunta:
    """Uma pergunta de teste e o que se espera achar no trecho que a responde."""

    texto: str
    termos: Tuple[str, ...]   # basta um deles aparecer no trecho (alternativas, por exemplo em inglês e em português)
    fonte: str = ""           # opcional: parte do nome do livro de onde o trecho deve vir


# Ponto de partida: termos de D&D 5e em inglês (com alternativas em português). Confira se existem nos seus livros.
PERGUNTAS_DE_EXEMPLO = [
    Pergunta("Como funciona a condição Agarrado?", ("Grappled", "Agarrado")),
    Pergunta("Quanto tempo dura um descanso longo?", ("at least 8 hours", "8 hours long", "pelo menos 8 horas")),
    Pergunta("O que é vantagem em um teste?", ("two d20", "second d20", "dois d20", "segundo d20")),
    Pergunta("Como funciona o ataque de oportunidade?",
             ("leaves your reach", "moves out of your reach", "sai do seu alcance")),
    Pergunta("O que é uma salvaguarda contra morte?", ("three successes", "3 successes", "três sucessos")),
    Pergunta("Qual o dano de uma queda?", ("every 10 feet", "10 feet you fall", "cada 10 pés", "cada 3 metros")),
    Pergunta("Como funciona a iniciativa?",
             ("roll Initiative", "rolls Initiative", "role iniciativa", "rolar iniciativa")),
    Pergunta("Como funciona a concentração em magias?", ("Constitution saving throw", "salvaguarda de Constituição")),
    Pergunta("Quais são as escolas de magia?", ("Abjuration", "Abjuração")),
    Pergunta("O que faz um Bárbaro?", ("Rage", "Fúria")),
    Pergunta("Quais raças posso escolher para o meu personagem?", ("Dragonborn", "Draconato")),
    Pergunta("Como funciona a ação de Esquivar?",
             ("Dodge action", "action Dodge", "ação Esquivar", "ação de Esquivar")),
]


@dataclass(frozen=True)
class Resultado:
    """O que a busca fez com uma pergunta."""

    pergunta: Pergunta
    posicao: Optional[int]                 # posição (1 = melhor) do primeiro trecho que acertou; None se nenhum acertou
    melhor_similaridade: Optional[float]   # similaridade do trecho mais parecido (None se a busca não trouxe nada)
    primeiro_trecho: Optional[Trecho]      # o trecho mais parecido, para ajudar a entender as falhas


@dataclass(frozen=True)
class Resumo:
    """Os números do relatório."""

    total: int
    k: int
    acertos_em_1: int    # o melhor trecho acertou
    acertos_em_3: int    # algum dos 3 primeiros acertou
    acertos_em_k: int    # algum dos k trechos acertou
    mrr: float           # média de 1/posição (0 se não acertou); 1.00 significa sempre em 1º lugar


def _limpar(texto: str) -> str:
    """Texto comparável: minúsculas, sem acentos e com qualquer sequência de espaços ou quebras de linha virando um espaço."""
    return re.sub(r"\s+", " ", normalizar(texto)).strip()


def _contem_termo(texto_limpo: str, termo: str) -> bool:
    """O termo aparece no texto como palavra inteira? ("Rage" não conta dentro de "average".)"""
    termo_limpo = _limpar(termo)
    return bool(termo_limpo) and re.search(rf"(?<!\w){re.escape(termo_limpo)}(?!\w)", texto_limpo) is not None


def trecho_confere(trecho: Trecho, pergunta: Pergunta) -> bool:
    """O trecho tem algum dos termos esperados e, se a pergunta indica um livro, vem desse livro?"""
    texto = _limpar(trecho.texto)
    if not any(_contem_termo(texto, termo) for termo in pergunta.termos):
        return False
    return not pergunta.fonte or _limpar(pergunta.fonte) in _limpar(trecho.fonte)


def ler_perguntas(caminho: Path) -> List[Pergunta]:
    """
    Lê um arquivo de perguntas no formato  pergunta | termo 1 ; termo 2 | livro (opcional).
    Linhas vazias e as que começam com # são ignoradas. Levanta ValueError, dizendo a linha, se algo estiver errado.
    """
    perguntas: List[Pergunta] = []
    for numero, linha in enumerate(caminho.read_text(encoding="utf-8").splitlines(), start=1):
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        partes = [parte.strip() for parte in linha.split("|")]
        if len(partes) < 2 or not partes[0]:
            raise ValueError(f"Linha {numero}: use  pergunta | termo 1 ; termo 2 | livro (opcional)")
        termos = tuple(termo.strip() for termo in partes[1].split(";") if termo.strip())
        if not termos:
            raise ValueError(f"Linha {numero}: informe pelo menos um termo esperado depois do primeiro |")
        perguntas.append(Pergunta(partes[0], termos, partes[2] if len(partes) > 2 else ""))
    if not perguntas:
        raise ValueError(f"{caminho.name}: nenhuma pergunta encontrada.")
    return perguntas


def avaliar(perguntas: Sequence[Pergunta], k: int,
            buscar: Optional[Callable[[str, int], List[Trecho]]] = None) -> List[Resultado]:
    """
    Roda cada pergunta na busca e confere em que posição aparece o primeiro trecho que acerta.
    `buscar` (padrão: rag.buscar_trechos) pode ser trocada nos testes. Levanta BaseVaziaError se os livros
    ainda não foram indexados.
    """
    buscar = buscar or rag.buscar_trechos
    resultados: List[Resultado] = []
    for pergunta in perguntas:
        trechos = buscar(pergunta.texto, k)
        posicao = next((i for i, trecho in enumerate(trechos, start=1) if trecho_confere(trecho, pergunta)), None)
        melhor = max((trecho.similaridade for trecho in trechos), default=None)
        resultados.append(Resultado(pergunta, posicao, melhor, trechos[0] if trechos else None))
    return resultados


def resumir(resultados: Sequence[Resultado], k: int) -> Resumo:
    """Conta os acertos por posição e calcula o MRR."""
    posicoes = [r.posicao for r in resultados]
    total = len(resultados)
    return Resumo(
        total=total,
        k=k,
        acertos_em_1=sum(1 for p in posicoes if p == 1),
        acertos_em_3=sum(1 for p in posicoes if p is not None and p <= 3),
        acertos_em_k=sum(1 for p in posicoes if p is not None),
        mrr=(sum(1 / p for p in posicoes if p) / total) if total else 0.0,
    )


def _porcentagem(parte: int, total: int) -> str:
    return f"{parte / total:.0%}" if total else "-"


def imprimir_relatorio(resultados: Sequence[Resultado], resumo: Resumo) -> None:
    """Mostra uma linha por pergunta, os detalhes das que falharam e o resumo."""
    print(f"Perguntas (k = {resumo.k}). Posição 1 é o melhor; \"falhou\" é nenhum acerto entre os {resumo.k} trechos:\n")
    for resultado in resultados:
        posicao = f"#{resultado.posicao}" if resultado.posicao else "falhou"
        similaridade = f"{resultado.melhor_similaridade:.2f}" if resultado.melhor_similaridade is not None else "--"
        print(f"  {posicao:<7} {similaridade:>5}  {resultado.pergunta.texto}")

    falhas = [r for r in resultados if r.posicao is None]
    if falhas:
        print("\nPERGUNTAS SEM ACERTO (confira se os termos esperados existem no seu livro):")
        for resultado in falhas:
            print(f"  - {resultado.pergunta.texto}")
            print(f"      termos esperados: {' ; '.join(resultado.pergunta.termos)}")
            if resultado.pergunta.fonte:
                print(f"      livro esperado: {resultado.pergunta.fonte}")
            trecho = resultado.primeiro_trecho
            if trecho is not None:
                trecho_curto = " ".join(trecho.texto.split())[:160]
                print(f"      trecho mais parecido: {trecho.fonte} ({trecho.similaridade:.2f}): \"{trecho_curto}\"")

    print(f"\nRESUMO ({resumo.total} perguntas, k = {resumo.k})")
    print(f"  Acertou em 1º lugar:            {resumo.acertos_em_1} de {resumo.total} ({_porcentagem(resumo.acertos_em_1, resumo.total)})")
    print(f"  Acertou entre os 3 primeiros:   {resumo.acertos_em_3} de {resumo.total} ({_porcentagem(resumo.acertos_em_3, resumo.total)})")
    print(f"  Acertou entre os {resumo.k} primeiros:   {resumo.acertos_em_k} de {resumo.total} ({_porcentagem(resumo.acertos_em_k, resumo.total)})")
    print(f"  MRR (média de 1/posição):       {resumo.mrr:.2f}  (1.00 = sempre em 1º lugar)")
    if falhas:
        print("\nSe o trecho mais parecido de uma falha trata do assunto certo, mas sem o termo esperado, ajuste o termo.")
        print("Se ele é de outro assunto, a busca errou: veja chunk_size e chunk_overlap em rpgassistant/config.py.")


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Ponto de entrada de `python -m rpgassistant.avaliar_recuperacao`. Devolve 0 se avaliou e 1 se não deu."""
    parser = argparse.ArgumentParser(description="Mede se a busca nos livros encontra o trecho certo para cada pergunta.")
    parser.add_argument("--perguntas", type=Path, help="arquivo com  pergunta | termo 1 ; termo 2 | livro (opcional)")
    parser.add_argument("--k", type=int, help="quantos trechos a busca traz (padrão: top_k_assistente)")
    args = parser.parse_args(argv)

    configurar_logs()
    k = args.k if args.k is not None else config.settings.top_k_assistente
    if k < 1:
        print("ERRO: --k precisa ser 1 ou mais.")
        return 1
    try:
        perguntas = ler_perguntas(args.perguntas) if args.perguntas else PERGUNTAS_DE_EXEMPLO
    except (OSError, ValueError) as e:
        print(f"ERRO: {e}")
        return 1
    try:
        resultados = avaliar(perguntas, k)
    except BaseVaziaError as e:
        # Sem livros indexados não há o que medir; a mensagem do erro já diz o comando para indexar.
        print(e)
        return 1
    imprimir_relatorio(resultados, resumir(resultados, k))
    return 0


if __name__ == "__main__":
    sys.exit(main())