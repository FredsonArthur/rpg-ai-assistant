"""
Diagnóstico da instalação
-------------------------
Mostra, em texto simples, tudo que costuma dar errado em uma instalação nova: versão do Python,
bibliotecas, livros, base vetorial, banco de chats e Ollama. Útil para pedir ajuda: copie a saída.

Uso:  python -m rpgassistant.diagnostico
"""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from rpgassistant import ambiente, config
from rpgassistant.logs import configurar_logs
from rpgassistant.services import ollama_service


@dataclass
class Diagnostico:
    python: str
    executavel: str
    sistema: str
    dependencias: List[Tuple[str, Optional[str]]]       # (pacote, versão ou None se não instalado)
    livros: Dict[str, int]                              # quantidade de arquivos por pasta
    base_vetorial: bool
    chats: Optional[int]                                # None se o banco ainda não existe
    ollama_ativo: bool
    modelo: str
    modelos_instalados: Optional[List[str]]             # None se não deu para consultar o Ollama
    configuracao: Dict[str, object] = field(default_factory=dict)
    erro_banco: str = ""


def _listar_modelos() -> Optional[List[str]]:
    """Nomes dos modelos baixados no Ollama (aceita os formatos antigo e novo da biblioteca)."""
    try:
        import ollama
        resposta = ollama.list()
    except Exception:
        return None
    modelos = getattr(resposta, "models", None)
    if modelos is None and isinstance(resposta, dict):
        modelos = resposta.get("models")
    nomes: List[str] = []
    for modelo in modelos or []:
        nome = getattr(modelo, "model", None)
        if nome is None and isinstance(modelo, dict):
            nome = modelo.get("model") or modelo.get("name")
        if nome:
            nomes.append(str(nome))
    return nomes


def modelo_instalado(modelo: str, instalados: List[str]) -> bool:
    """"llama3" conta como instalado se existir "llama3" ou "llama3:latest" (ou outra variante)."""
    return any(nome == modelo or nome.startswith(modelo + ":") for nome in instalados)


def _contar_livros() -> Dict[str, int]:
    base = config.settings.rulebooks_dir
    contagem: Dict[str, int] = {}
    for subpasta in ("core", "suplements"):
        pasta = base / subpasta
        contagem[subpasta] = sum(1 for p in pasta.rglob("*") if p.suffix.lower() in (".md", ".pdf")) if pasta.is_dir() else 0
    return contagem


def _contar_chats() -> Tuple[Optional[int], str]:
    caminho = config.settings.chats_db
    if not caminho.exists():
        return None, ""
    try:
        from rpgassistant.storage.database import Database
        with Database(caminho) as db:
            return db.valor("SELECT COUNT(*) FROM chats"), ""
    except Exception as e:
        return None, str(e)


def coletar(versao_do_pacote: Callable[[str], Optional[str]] = ambiente.versao_instalada,
            ollama_ativo: Callable[[], bool] = ollama_service.ollama_ativo,
            listar_modelos: Callable[[], Optional[List[str]]] = _listar_modelos) -> Diagnostico:
    cfg = config.settings
    ativo = ollama_ativo()
    chats, erro_banco = _contar_chats()
    pasta_vetorial = cfg.vectordb_dir
    return Diagnostico(
        python=platform.python_version(),
        executavel=sys.executable,
        sistema=f"{platform.system()} {platform.release()}",
        dependencias=[(pacote, versao_do_pacote(pacote)) for _, pacote in ambiente.DEPENDENCIAS],
        livros=_contar_livros(),
        base_vetorial=pasta_vetorial.is_dir() and any(pasta_vetorial.iterdir()),
        chats=chats,
        erro_banco=erro_banco,
        ollama_ativo=ativo,
        modelo=cfg.ollama_model,
        modelos_instalados=listar_modelos() if ativo else None,
        configuracao={"relevancia_minima": cfg.relevancia_minima, "ollama_num_ctx": cfg.ollama_num_ctx,
                      "pasta_de_dados": str(cfg.data_dir)},
    )


def problemas(d: Diagnostico) -> List[str]:
    """O que precisa de atenção, com o comando para resolver."""
    versao = tuple(int(n) for n in d.python.split(".")[:3])
    achados = [p.texto for p in ambiente.verificar_python(versao)]
    ausentes = [pacote for pacote, v in d.dependencias if v is None]
    if ausentes:
        achados.append(f"Bibliotecas não instaladas neste Python: {', '.join(ausentes)}. Rode: {ambiente.COMANDO_INSTALAR}")
    if d.erro_banco:
        achados.append(f"O banco de chats não abriu: {d.erro_banco}")
    if sum(d.livros.values()) == 0:
        achados.append(f"Nenhum livro em {config.settings.rulebooks_dir}. Coloque arquivos .md ou .pdf em core/ e suplements/.")
    elif not d.base_vetorial:
        achados.append("Os livros ainda não foram indexados. Rode: python -m rpgassistant.indexar")
    if not d.ollama_ativo:
        achados.append("O Ollama não está respondendo. Inicie-o com: ollama serve")
    elif d.modelos_instalados is not None and not modelo_instalado(d.modelo, d.modelos_instalados):
        achados.append(f"O modelo {d.modelo} não está baixado. Rode: ollama pull {d.modelo}")
    return achados


def formatar(d: Diagnostico) -> str:
    def marca(ok: bool) -> str:
        return "[ok]" if ok else "[!!]"

    linhas = [
        "DIAGNÓSTICO DO RPG AI ASSISTANT",
        "",
        f"Python:    {d.python}  ({d.executavel})",
        f"Sistema:   {d.sistema}",
        "",
        "Bibliotecas:",
    ]
    linhas += [f"  {marca(v is not None)} {pacote} {v or 'NÃO INSTALADO'}" for pacote, v in d.dependencias]
    linhas += [
        "",
        "Dados:",
        f"  {marca(sum(d.livros.values()) > 0)} Livros: core={d.livros.get('core', 0)}, suplements={d.livros.get('suplements', 0)}",
        f"  {marca(d.base_vetorial)} Base vetorial: {'indexada' if d.base_vetorial else 'ainda não indexada'}",
        f"  {marca(not d.erro_banco)} Banco de chats: "
        + (d.erro_banco if d.erro_banco else ("ainda não criado" if d.chats is None else f"{d.chats} chat(s)")),
        "",
        "Ollama:",
        f"  {marca(d.ollama_ativo)} Serviço: {'respondendo' if d.ollama_ativo else 'NÃO está respondendo'}",
    ]
    if d.modelos_instalados is not None:
        linhas.append(f"  {marca(modelo_instalado(d.modelo, d.modelos_instalados))} Modelo {d.modelo}: "
                      f"{'baixado' if modelo_instalado(d.modelo, d.modelos_instalados) else 'NÃO baixado'}"
                      f"  (instalados: {', '.join(d.modelos_instalados) or 'nenhum'})")
    linhas += ["", "Configuração: " + ", ".join(f"{k}={v}" for k, v in d.configuracao.items()), ""]

    achados = problemas(d)
    if achados:
        linhas.append("O QUE PRECISA DE ATENÇÃO:")
        linhas += [f"  - {a}" for a in achados]
    else:
        linhas.append("Tudo certo: nenhum problema encontrado.")
    return "\n".join(linhas)


def main() -> int:
    configurar_logs()
    print(formatar(coletar()))
    return 0


if __name__ == "__main__":
    sys.exit(main())