import contextlib
import io
import sys
import types
import unittest
from unittest import mock

import main
from rpgassistant import ambiente
from tests.helpers import BaseTeste


class VerificarPythonTest(unittest.TestCase):
    def test_versoes_adequadas(self):
        for versao in ((3, 10, 0), (3, 12, 4), (3, 13, 9)):
            with self.subTest(versao=versao):
                self.assertEqual(ambiente.verificar_python(versao), [])

    def test_python_antigo_e_um_erro(self):
        problemas = ambiente.verificar_python((3, 9, 18))
        self.assertEqual([p.gravidade for p in problemas], ["erro"])
        self.assertIn("3.12", problemas[0].texto)

    def test_python_muito_novo_so_avisa_e_diz_qual_usar(self):
        for versao in ((3, 14, 0), (3, 15, 0)):
            with self.subTest(versao=versao):
                problemas = ambiente.verificar_python(versao)
                self.assertEqual([p.gravidade for p in problemas], ["aviso"])
                self.assertIn("compilador C++", problemas[0].texto)
                self.assertIn("3.12", problemas[0].texto)


class DependenciasTest(unittest.TestCase):
    def test_tudo_instalado(self):
        self.assertEqual(ambiente.dependencias_ausentes(lambda modulo: object()), [])
        self.assertEqual(ambiente.verificar_ambiente((3, 12, 0), lambda modulo: object()), [])

    def test_lista_os_pacotes_do_pip_que_faltam(self):
        ausentes = {"PySide6", "langchain_chroma"}
        achar = lambda modulo: None if modulo in ausentes else object()
        self.assertEqual(ambiente.dependencias_ausentes(achar), ["PySide6", "langchain-chroma"])

    def test_mensagem_de_erro_explica_o_que_fazer(self):
        problemas = ambiente.verificar_ambiente((3, 12, 0), lambda modulo: None)
        self.assertEqual([p.gravidade for p in problemas], ["erro"])
        texto = problemas[0].texto
        self.assertIn("pip install -r requirements.txt", texto)
        self.assertIn("Select Interpreter", texto)
        self.assertIn("PySide6", texto)

    def test_python_novo_com_bibliotecas_faltando_mostra_os_dois(self):
        problemas = ambiente.verificar_ambiente((3, 15, 0), lambda modulo: None)
        self.assertEqual([p.gravidade for p in problemas], ["aviso", "erro"])

    def test_todos_os_pacotes_do_requirements_estao_na_verificacao(self):
        import pathlib
        import re
        requisitos = pathlib.Path(__file__).resolve().parent.parent / "requirements.txt"
        pacotes = {re.split(r"[<>=]", linha)[0].strip().lower()
                   for linha in requisitos.read_text(encoding="utf-8").splitlines()
                   if linha.strip() and not linha.startswith("#")}
        verificados = {pacote.lower() for _, pacote in ambiente.DEPENDENCIAS}
        self.assertEqual(pacotes, verificados)

    def test_versao_instalada(self):
        self.assertIsNone(ambiente.versao_instalada("pacote-que-nao-existe-xyz"))


class MainTest(BaseTeste):
    def test_erro_de_ambiente_para_com_mensagem_e_codigo_1(self):
        erro = io.StringIO()
        problemas = [ambiente.Problema("erro", "Faltam bibliotecas: PySide6.")]
        with mock.patch.object(ambiente, "verificar_ambiente", return_value=problemas), contextlib.redirect_stderr(erro):
            codigo = main.main()
        self.assertEqual(codigo, 1)
        self.assertIn("ERRO: Faltam bibliotecas: PySide6.", erro.getvalue())
        self.assertIn("python -m rpgassistant.diagnostico", erro.getvalue())

    def test_aviso_nao_impede_a_abertura(self):
        """Com só um aviso, o programa segue para a abertura da janela (aqui interrompida por um Qt de mentira)."""
        class Parou(Exception):
            pass

        def aplicativo_falso(*args, **kwargs):
            raise Parou()

        qt = types.ModuleType("PySide6.QtWidgets")
        qt.QApplication = aplicativo_falso
        qt.QMessageBox = mock.Mock()
        erro = io.StringIO()
        problemas = [ambiente.Problema("aviso", "Python novo.")]
        with mock.patch.object(ambiente, "verificar_ambiente", return_value=problemas), \
             mock.patch.dict(sys.modules, {"PySide6": types.ModuleType("PySide6"), "PySide6.QtWidgets": qt}), \
             contextlib.redirect_stderr(erro):
            with self.assertRaises((Parou, ImportError)):
                main.main()
        self.assertIn("AVISO: Python novo.", erro.getvalue())
        self.assertTrue(self.cfg.rulebooks_dir.is_dir())  # a pasta de dados foi preparada antes de abrir a janela


if __name__ == "__main__":
    unittest.main()