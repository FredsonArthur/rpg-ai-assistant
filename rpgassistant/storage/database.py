"""
Banco de dados SQLite
---------------------
Abre (e cria, se preciso) o banco local de chats, aplica as migrações de esquema e oferece
transações seguras. Só usa a biblioteca padrão do Python.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, List, Sequence, Tuple, Union

from rpgassistant.errors import BancoDeDadosError

logger = logging.getLogger(__name__)

MEMORIA = ":memory:"

# Cada migração é uma lista de comandos SQL. A posição na lista é a versão do esquema
# (PRAGMA user_version): para mudar o esquema no futuro, acrescente uma nova migração ao final.
MIGRACOES: List[Tuple[str, ...]] = [
    (
        """
        CREATE TABLE chats (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo        TEXT NOT NULL,
            modo          TEXT,
            estado        TEXT NOT NULL DEFAULT '{}',
            criado_em     TEXT NOT NULL,
            atualizado_em TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE mensagens (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id   INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
            ordem     INTEGER NOT NULL,
            papel     TEXT NOT NULL,
            tipo      TEXT NOT NULL DEFAULT 'fala',
            conteudo  TEXT NOT NULL,
            extras    TEXT NOT NULL DEFAULT '{}',
            criado_em TEXT NOT NULL,
            UNIQUE (chat_id, ordem)
        )
        """,
        "CREATE INDEX idx_chats_atualizado ON chats (atualizado_em DESC)",
    ),
]
VERSAO_ATUAL = len(MIGRACOES)


class Database:
    """Conexão única e protegida por trava, pensada para uso a partir de uma interface gráfica."""

    def __init__(self, caminho: Union[str, Path] = MEMORIA) -> None:
        self.caminho = str(caminho)
        self._lock = threading.RLock()
        self._profundidade = 0  # transações aninhadas viram uma só
        self._conn: sqlite3.Connection

        if self.caminho != MEMORIA:
            Path(self.caminho).parent.mkdir(parents=True, exist_ok=True)

        try:
            # isolation_level=None: controlamos as transações explicitamente (BEGIN/COMMIT).
            self._conn = sqlite3.connect(self.caminho, isolation_level=None, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            if self.caminho != MEMORIA:
                self._conn.execute("PRAGMA journal_mode = WAL")  # leituras não travam as gravações
            resultado = self._conn.execute("PRAGMA quick_check").fetchone()[0]
            if resultado != "ok":
                raise BancoDeDadosError(f"O banco de chats parece corrompido ({resultado}).")
            self._migrar()
        except sqlite3.DatabaseError as e:
            self.fechar()
            raise BancoDeDadosError(
                f"Não foi possível abrir o banco de chats em {self.caminho}: {e}. "
                "Se o arquivo estiver danificado, renomeie-o para guardar uma cópia e abra o app de novo."
            ) from e
        except BancoDeDadosError:
            self.fechar()
            raise

    def _migrar(self) -> None:
        versao = self._conn.execute("PRAGMA user_version").fetchone()[0]
        if versao > VERSAO_ATUAL:
            raise BancoDeDadosError(
                f"O banco de chats foi criado por uma versão mais nova do app (esquema {versao}, "
                f"esta versão entende até o {VERSAO_ATUAL}). Atualize o app."
            )
        for indice in range(versao, VERSAO_ATUAL):
            logger.info("Aplicando a migração %d do banco de chats", indice + 1)
            with self.transaction():
                for comando in MIGRACOES[indice]:
                    self._conn.execute(comando)
                self._conn.execute(f"PRAGMA user_version = {indice + 1}")

    @property
    def versao(self) -> int:
        return self._conn.execute("PRAGMA user_version").fetchone()[0]

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Agrupa várias operações: ou todas valem, ou nenhuma (desfaz se algo der erro)."""
        with self._lock:
            if self._profundidade > 0:
                yield
                return
            self._conn.execute("BEGIN IMMEDIATE")
            self._profundidade = 1
            try:
                yield
            except BaseException:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.OperationalError:
                    pass  # o SQLite já tinha desfeito a transação sozinho
                raise
            else:
                self._conn.execute("COMMIT")
            finally:
                self._profundidade = 0

    def executar(self, sql: str, parametros: Sequence[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, tuple(parametros))

    def consultar(self, sql: str, parametros: Sequence[Any] = ()) -> List[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, tuple(parametros)).fetchall()

    def valor(self, sql: str, parametros: Sequence[Any] = ()) -> Any:
        """Primeiro valor da primeira linha do resultado (ou None)."""
        linhas = self.consultar(sql, parametros)
        return linhas[0][0] if linhas else None

    def fechar(self) -> None:
        conn = getattr(self, "_conn", None)
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *args: Any) -> None:
        self.fechar()