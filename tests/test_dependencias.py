"""
Dependências do projeto
-----------------------
- requirements.txt: as bibliotecas que o projeto usa, com versões MÍNIMAS (é o jeito normal de instalar).
- requirements-lock.txt: o ambiente de referência, com versões EXATAS (para reproduzir o que foi testado).

Estes testes impedem que os dois arquivos fiquem em desacordo (por exemplo, uma biblioteca nova que entrou
no requirements.txt e ficou de fora do lock) e que o lock contenha algo que não instala fora do Linux.
"""

import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LINHA = re.compile(r"^([A-Za-z0-9._-]+)\s*(==|>=)\s*([^\s;]+)\s*(?:;.*)?$")


def normalizar(nome: str) -> str:
    """Nome de pacote comparável: minúsculas, com hífen no lugar de ponto e sublinhado (como o pip faz)."""
    return re.sub(r"[-_.]+", "-", nome).lower()


def versao(texto: str) -> tuple:
    """Versão como tupla de números, para comparar ("6.12.0" > "6.6.0"). Ignora a parte local depois do "+"."""
    return tuple(int(parte) for parte in re.findall(r"\d+", texto.split("+")[0]))


def ler(nome_do_arquivo: str):
    """
    Lê um arquivo de requisitos. Devolve (requisitos, linhas_invalidas), em que `requisitos` mapeia o nome
    normalizado do pacote para (operador, versão, linha original).
    """
    requisitos, invalidas = {}, []
    for linha in (RAIZ / nome_do_arquivo).read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        achado = LINHA.match(linha)
        if not achado:
            invalidas.append(linha)
            continue
        nome, operador, numero = achado.groups()
        requisitos[normalizar(nome)] = (operador, numero, linha)
    return requisitos, invalidas


class LockTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.minimos, cls.minimos_invalidos = ler("requirements.txt")
        cls.lock, cls.lock_invalido = ler("requirements-lock.txt")

    def test_os_arquivos_sao_legiveis(self):
        self.assertEqual(self.minimos_invalidos, [])
        self.assertEqual(self.lock_invalido, [])
        self.assertTrue(self.minimos and self.lock)

    def test_toda_linha_do_lock_tem_versao_exata(self):
        fora_do_padrao = [linha for _, (operador, _, linha) in self.lock.items() if operador != "=="]
        self.assertEqual(fora_do_padrao, [])

    def test_todo_requisito_do_projeto_esta_no_lock(self):
        faltando = sorted(nome for nome in self.minimos if nome not in self.lock)
        self.assertEqual(faltando, [], "estas bibliotecas estão no requirements.txt, mas não no lock")

    def test_a_versao_do_lock_atende_o_minimo_do_requirements(self):
        for nome, (_, minimo, _) in self.minimos.items():
            with self.subTest(pacote=nome):
                self.assertIn(nome, self.lock)  # se faltar, o teste acima já explica; aqui só evita um KeyError
                _, fixada, _ = self.lock[nome]
                self.assertGreaterEqual(versao(fixada), versao(minimo))

    def test_o_pytorch_fica_de_fora_e_nao_ha_versoes_locais(self):
        """O PyTorch para CPU (2.x.y+cpu) vem de outro endereço e é instalado à parte, antes do lock."""
        self.assertNotIn("torch", self.lock)
        com_versao_local = [linha for _, (_, numero, linha) in self.lock.items() if "+" in numero]
        self.assertEqual(com_versao_local, [])

    def test_uvloop_so_fora_do_windows(self):
        """O uvloop não existe para Windows: sem o marcador, o lock não instalaria lá."""
        if "uvloop" in self.lock:
            self.assertIn('sys_platform != "win32"', self.lock["uvloop"][2])


if __name__ == "__main__":
    unittest.main()