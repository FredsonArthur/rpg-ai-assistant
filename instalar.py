"""
Instalador do RPG AI Assistant
------------------------------
Prepara tudo com um comando, em qualquer pasta e em qualquer sistema:

    python instalar.py            (no Windows também funciona:  py instalar.py)

O que ele faz:
1. Procura um Python compatível (3.10 a 3.13) no computador. Se o Python que você usou para rodar este
   arquivo for novo demais, ele tenta achar outro sozinho (por exemplo, o 3.12).
2. Cria (ou recria, se foi feito com um Python incompatível) o ambiente virtual "venv" dentro do projeto.
3. Instala as bibliotecas de requirements.txt.
4. Roda o diagnóstico, que mostra o que ainda falta (livros, Ollama, modelo...).

Usa só a biblioteca padrão do Python, então roda mesmo antes de qualquer instalação.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, List, Optional, Tuple

RAIZ = Path(__file__).resolve().parent
VERSAO_MINIMA = (3, 10)
VERSAO_MAXIMA = (3, 13)
PREFERIDAS = ("3.12", "3.13", "3.11", "3.10")
LINK_PYTHON = "https://www.python.org/downloads/"

Versao = Tuple[int, int]
Comando = List[str]


def _utf8() -> None:
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def versao_do_python(comando: Comando) -> Optional[Versao]:
    """Versão (maior, menor) do Python que o comando executa, ou None se ele não existir ou falhar."""
    try:
        saida = subprocess.run(
            comando + ["-c", "import sys; print(sys.version_info[0], sys.version_info[1])"],
            capture_output=True, text=True, timeout=30,
        )
        maior, menor = saida.stdout.split()[:2]
        return int(maior), int(menor)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def versao_aceita(versao: Optional[Versao]) -> bool:
    return versao is not None and VERSAO_MINIMA <= versao <= VERSAO_MAXIMA


def candidatos() -> List[Comando]:
    """Pythons que vale a pena testar: o atual primeiro, depois os instalados na máquina."""
    lista: List[Comando] = [[sys.executable]]
    for versao in PREFERIDAS:
        if sys.platform == "win32":
            lista.append(["py", f"-{versao}"])  # o "py launcher" do Windows escolhe a versão pedida
        elif shutil.which(f"python{versao}"):
            lista.append([f"python{versao}"])
    return lista


def escolher_python(lista: List[Comando], versao_de: Callable[[Comando], Optional[Versao]] = versao_do_python) -> Optional[Comando]:
    for comando in lista:
        if versao_aceita(versao_de(comando)):
            return comando
    return None


def python_do_venv(raiz: Optional[Path] = None) -> Path:
    raiz = raiz or RAIZ
    return raiz / "venv" / ("Scripts" if sys.platform == "win32" else "bin") / ("python.exe" if sys.platform == "win32" else "python")


def executar(comando: Comando, titulo: str, fatal: bool = True) -> bool:
    print(f"\n==> {titulo}")
    print("    " + " ".join(comando))
    if subprocess.run(comando, cwd=str(RAIZ)).returncode == 0:
        return True
    print(f"\n{'ERRO' if fatal else 'AVISO'}: o passo \"{titulo}\" falhou.")
    return False


def main(versao_de: Callable[[Comando], Optional[Versao]] = versao_do_python) -> int:
    _utf8()
    print("Instalador do RPG AI Assistant")
    print(f"Pasta do projeto: {RAIZ}")

    if not (RAIZ / "requirements.txt").exists():
        print("\nERRO: não achei o requirements.txt ao lado deste arquivo. Rode o instalador de dentro da pasta do projeto.")
        return 1

    python = escolher_python(candidatos(), versao_de)
    if python is None:
        print("\nERRO: não encontrei no computador um Python entre 3.10 e 3.13 (recomendado: 3.12).")
        print("Versões mais novas ainda não têm pacote pronto para todas as bibliotecas e a instalação falha.")
        print(f"Instale o Python 3.12 em {LINK_PYTHON} (no Windows, marque \"Add python.exe to PATH\") e rode este arquivo de novo.")
        return 1
    versao = versao_de(python)
    print(f"\nPython escolhido: {' '.join(python)} (versão {versao[0]}.{versao[1]})")

    venv_python = python_do_venv()
    if venv_python.exists() and not versao_aceita(versao_de([str(venv_python)])):
        print("\nO ambiente virtual existente foi criado com um Python incompatível. Vou recriá-lo.")
        shutil.rmtree(RAIZ / "venv", ignore_errors=True)
    if not venv_python.exists():
        if not executar(python + ["-m", "venv", "venv"], "Criando o ambiente virtual"):
            return 1

    pip = [str(venv_python), "-m", "pip"]
    executar(pip + ["install", "--upgrade", "pip"], "Atualizando o pip", fatal=False)
    if sys.platform.startswith("linux"):
        # No Linux o pacote padrão do PyTorch traz bibliotecas de GPU (vários GB); a versão para CPU basta aqui.
        executar(pip + ["install", "torch", "--index-url", "https://download.pytorch.org/whl/cpu"],
                 "Instalando o PyTorch para CPU (opcional)", fatal=False)
    if not executar(pip + ["install", "-r", "requirements.txt"], "Instalando as bibliotecas"):
        print("\nSe o erro mencionar \"Microsoft Visual C++\" ou \"Failed to build\", o Python usado é novo demais.")
        print("Veja a seção \"Solução de problemas\" do README.")
        return 1

    executar([str(venv_python), "-m", "rpgassistant.diagnostico"], "Conferindo a instalação", fatal=False)

    ativar = r"venv\Scripts\activate" if sys.platform == "win32" else "source venv/bin/activate"
    print("\nPronto. Próximos passos (dentro da pasta do projeto):")
    print(f"  1. {ativar}")
    print("  2. Coloque os livros em data/rulebooks/core e data/rulebooks/suplements")
    print("  3. python -m rpgassistant.indexar")
    print("  4. python main.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())