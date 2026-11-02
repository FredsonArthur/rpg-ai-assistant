import io
import sys
import unittest
from unittest import mock

from rpgassistant import logs


class SaidaUtf8Test(unittest.TestCase):
    def test_console_sem_utf8_nao_quebra_com_acentos_e_emojis(self):
        bruto = io.BytesIO()
        console = io.TextIOWrapper(bruto, encoding="cp1252", errors="strict")
        with mock.patch.object(sys, "stdout", console), mock.patch.object(sys, "stderr", io.StringIO()):
            logs._saida_em_utf8()
            print("Atenção: 🎲 ação")  # em cp1252 estrito, o emoji levantaria UnicodeEncodeError
            console.flush()
        self.assertIn("Atenção".encode("utf-8"), bruto.getvalue())

    def test_fluxo_sem_reconfigure_e_ignorado(self):
        class SemSuporte:
            pass
        with mock.patch.object(sys, "stdout", SemSuporte()), mock.patch.object(sys, "stderr", SemSuporte()):
            logs._saida_em_utf8()  # não deve levantar erro


if __name__ == "__main__":
    unittest.main()