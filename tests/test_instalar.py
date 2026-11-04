import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import instalar


class VersaoTest(unittest.TestCase):
    def test_versao_aceita(self):
        for versao, esperado in (((3, 9), False), ((3, 10), True), ((3, 12), True), ((3, 13), True),
                                 ((3, 14), False), ((3, 15), False), (None, False)):
            with self.subTest(versao=versao):
                self.assertEqual(instalar.versao_aceita(versao), esperado)

    def test_escolher_python_pega_o_primeiro_compativel(self):
        versoes = {("atual",): (3, 15), ("py", "-3.12"): (3, 12), ("py", "-3.13"): (3, 13)}
        lista = [["atual"], ["py", "-3.12"], ["py", "-3.13"]]
        self.assertEqual(instalar.escolher_python(lista, lambda c: versoes.get(tuple(c))), ["py", "-3.12"])

    def test_o_python_atual_vale_se_for_compativel(self):
        self.assertEqual(instalar.escolher_python([["atual"], ["py", "-3.12"]], lambda c: (3, 13) if c == ["atual"] else (3, 12)), ["atual"])

    def test_nenhum_compativel(self):
        self.assertIsNone(instalar.escolher_python([["atual"], ["py", "-3.12"]], lambda c: None if c[0] == "py" else (3, 15)))

    def test_versao_do_python_de_um_executavel_de_verdade(self):
        versao = instalar.versao_do_python([sys.executable])
        self.assertEqual(versao, tuple(sys.version_info[:2]))
        self.assertIsNone(instalar.versao_do_python(["programa-que-nao-existe-xyz"]))


class CaminhosTest(unittest.TestCase):
    def test_candidatos_no_windows_usam_o_py_launcher(self):
        with mock.patch.object(sys, "platform", "win32"):
            lista = instalar.candidatos()
        self.assertEqual(lista[0], [sys.executable])
        self.assertIn(["py", "-3.12"], lista)

    def test_candidatos_no_linux_so_com_o_que_esta_instalado(self):
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch.object(instalar.shutil, "which", lambda nome: "/usr/bin/" + nome if nome == "python3.12" else None):
            lista = instalar.candidatos()
        self.assertEqual(lista, [[sys.executable], ["python3.12"]])

    def test_python_do_venv(self):
        raiz = Path("/projeto")
        with mock.patch.object(sys, "platform", "win32"):
            self.assertEqual(instalar.python_do_venv(raiz), raiz / "venv" / "Scripts" / "python.exe")
        with mock.patch.object(sys, "platform", "linux"):
            self.assertEqual(instalar.python_do_venv(raiz), raiz / "venv" / "bin" / "python")


class MainTest(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.raiz = Path(pasta.name)
        (self.raiz / "requirements.txt").write_text("pypdf\n", encoding="utf-8")
        mock.patch.object(instalar, "RAIZ", self.raiz).start()
        self.addCleanup(mock.patch.stopall)
        self.comandos = []
        self.falhas = set()   # trechos de comando que devem falhar

    def rodar(self, plataforma, versoes, candidatos):
        """Executa main() com um sistema e versões de Python simulados; devolve (código, saída)."""
        def falso(comando, cwd=None, **kwargs):
            self.comandos.append(comando)
            if comando[-2:] == ["venv", "venv"]:  # criar o venv cria o python dele
                alvo = instalar.python_do_venv(self.raiz)
                alvo.parent.mkdir(parents=True, exist_ok=True)
                alvo.write_text("")
            falhou = any(trecho in " ".join(comando) for trecho in self.falhas)
            return mock.Mock(returncode=1 if falhou else 0)

        saida = io.StringIO()
        with mock.patch.object(sys, "platform", plataforma), \
             mock.patch.object(instalar, "candidatos", return_value=candidatos), \
             mock.patch.object(instalar.subprocess, "run", falso), contextlib.redirect_stdout(saida):
            codigo = instalar.main(lambda c: versoes.get(tuple(c)))
        return codigo, saida.getvalue()

    def comando_com(self, trecho):
        return [c for c in self.comandos if trecho in " ".join(c)]

    def test_sem_requirements_para_com_instrucao(self):
        (self.raiz / "requirements.txt").unlink()
        codigo, saida = self.rodar("linux", {}, [])
        self.assertEqual(codigo, 1)
        self.assertIn("requirements.txt", saida)
        self.assertEqual(self.comandos, [])

    def test_windows_com_python_novo_usa_o_3_12(self):
        versoes = {("atual",): (3, 15), ("py", "-3.12"): (3, 12)}
        codigo, saida = self.rodar("win32", versoes, [["atual"], ["py", "-3.12"]])
        self.assertEqual(codigo, 0)
        self.assertEqual(self.comando_com("-m venv venv"), [["py", "-3.12", "-m", "venv", "venv"]])
        with mock.patch.object(sys, "platform", "win32"):
            venv_python = str(instalar.python_do_venv(self.raiz))
        self.assertTrue(any(c[0] == venv_python and c[-2:] == ["-r", "requirements.txt"] for c in self.comandos))
        self.assertTrue(any(c[:3] == [venv_python, "-m", "rpgassistant.diagnostico"] for c in self.comandos))
        self.assertEqual(self.comando_com("torch"), [])  # no Windows o pip já instala o PyTorch para CPU
        self.assertIn(r"venv\Scripts\activate", saida)
        self.assertIn("python main.py", saida)

    def test_nenhum_python_compativel(self):
        codigo, saida = self.rodar("win32", {("atual",): (3, 15)}, [["atual"], ["py", "-3.12"]])
        self.assertEqual(codigo, 1)
        self.assertIn("python.org", saida)
        self.assertIn("3.12", saida)
        self.assertEqual(self.comandos, [])

    def test_linux_tenta_o_pytorch_para_cpu_mas_continua_se_falhar(self):
        self.falhas = {"torch"}
        codigo, saida = self.rodar("linux", {("atual",): (3, 12)}, [["atual"]])
        self.assertEqual(codigo, 0)
        self.assertTrue(self.comando_com("download.pytorch.org/whl/cpu"))
        self.assertTrue(self.comando_com("-r requirements.txt"))
        self.assertIn("AVISO", saida)
        self.assertIn("source venv/bin/activate", saida)

    def test_falha_nas_bibliotecas_e_fatal_e_orienta(self):
        self.falhas = {"-r requirements.txt"}
        codigo, saida = self.rodar("linux", {("atual",): (3, 12)}, [["atual"]])
        self.assertEqual(codigo, 1)
        self.assertIn("Solução de problemas", saida)
        self.assertEqual(self.comando_com("rpgassistant.diagnostico"), [])

    def test_venv_incompativel_e_recriado(self):
        venv_python = instalar.python_do_venv(self.raiz)
        venv_python.parent.mkdir(parents=True)
        venv_python.write_text("")
        (self.raiz / "venv" / "marcador.txt").write_text("antigo")
        versoes = {("atual",): (3, 12), (str(venv_python),): (3, 15)}
        codigo, saida = self.rodar("linux", versoes, [["atual"]])
        self.assertEqual(codigo, 0)
        self.assertIn("recriá-lo", saida)
        self.assertFalse((self.raiz / "venv" / "marcador.txt").exists())
        self.assertTrue(self.comando_com("-m venv venv"))

    def test_venv_compativel_e_reaproveitado(self):
        venv_python = instalar.python_do_venv(self.raiz)
        venv_python.parent.mkdir(parents=True)
        venv_python.write_text("")
        versoes = {("atual",): (3, 12), (str(venv_python),): (3, 12)}
        codigo, _ = self.rodar("linux", versoes, [["atual"]])
        self.assertEqual(codigo, 0)
        self.assertEqual(self.comando_com("-m venv venv"), [])


if __name__ == "__main__":
    unittest.main()