import unittest
from unittest import mock

from rpgassistant import diagnostico
from tests.helpers import BaseTeste


def tudo_instalado(pacote):
    return "1.0.0"


class ModeloInstaladoTest(unittest.TestCase):
    def test_nomes(self):
        self.assertTrue(diagnostico.modelo_instalado("llama3", ["llama3:latest"]))
        self.assertTrue(diagnostico.modelo_instalado("llama3", ["llama3"]))
        self.assertTrue(diagnostico.modelo_instalado("llama3", ["qwen2.5:7b", "llama3:8b"]))
        self.assertFalse(diagnostico.modelo_instalado("llama3", ["llama3.1:8b"]))  # outro modelo, nome parecido
        self.assertFalse(diagnostico.modelo_instalado("llama3", []))


class ListarModelosTest(unittest.TestCase):
    def listar(self, resposta):
        modulo = mock.Mock()
        modulo.list.return_value = resposta
        with mock.patch.dict("sys.modules", {"ollama": modulo}):
            return diagnostico._listar_modelos()

    def test_formato_novo_com_objetos(self):
        modelos = [mock.Mock(model="llama3:latest"), mock.Mock(model="qwen2.5:7b")]
        self.assertEqual(self.listar(mock.Mock(models=modelos)), ["llama3:latest", "qwen2.5:7b"])

    def test_formato_antigo_com_dicionarios(self):
        self.assertEqual(self.listar({"models": [{"name": "llama3:latest"}, {"model": "mistral:7b"}]}),
                         ["llama3:latest", "mistral:7b"])

    def test_falha_devolve_none(self):
        modulo = mock.Mock()
        modulo.list.side_effect = ConnectionError("fora do ar")
        with mock.patch.dict("sys.modules", {"ollama": modulo}):
            self.assertIsNone(diagnostico._listar_modelos())


class DiagnosticoTest(BaseTeste):
    def coletar(self, versao=tudo_instalado, ativo=True, modelos=("llama3:latest",)):
        return diagnostico.coletar(versao, lambda: ativo, lambda: list(modelos) if modelos is not None else None)

    def preparar_dados(self):
        livro = self.cfg.rulebooks_dir / "core" / "PHB.md"
        livro.parent.mkdir(parents=True)
        livro.write_text("# livro", encoding="utf-8")
        (self.cfg.rulebooks_dir / "suplements").mkdir()
        (self.cfg.rulebooks_dir / "suplements" / "Tasha.pdf").write_bytes(b"%PDF")
        (self.cfg.rulebooks_dir / "core" / "anotacoes.txt").write_text("não conta", encoding="utf-8")
        self.cfg.vectordb_dir.mkdir()
        (self.cfg.vectordb_dir / "chroma.sqlite3").write_bytes(b"x")

    def test_instalacao_completa_nao_tem_problemas(self):
        self.preparar_dados()
        d = self.coletar()
        self.assertEqual(d.livros, {"core": 1, "suplements": 1})
        self.assertTrue(d.base_vetorial)
        self.assertIsNone(d.chats)
        problemas = [p for p in diagnostico.problemas(d) if "Python" not in p]  # a versão do Python de quem roda o teste varia
        self.assertEqual(problemas, [])

    def test_instalacao_vazia_lista_o_que_fazer(self):
        d = self.coletar(versao=lambda pacote: None, ativo=False, modelos=None)
        problemas = "\n".join(diagnostico.problemas(d))
        self.assertIn("pip install -r requirements.txt", problemas)
        self.assertIn("Nenhum livro", problemas)
        self.assertIn("ollama serve", problemas)
        saida = diagnostico.formatar(d)
        self.assertIn("PySide6 NÃO INSTALADO", saida)
        self.assertIn("O QUE PRECISA DE ATENÇÃO", saida)

    def test_livros_sem_base_vetorial(self):
        self.preparar_dados()
        for arquivo in self.cfg.vectordb_dir.iterdir():
            arquivo.unlink()
        self.assertIn("python -m rpgassistant.indexar", "\n".join(diagnostico.problemas(self.coletar())))

    def test_modelo_nao_baixado(self):
        self.preparar_dados()
        d = self.coletar(modelos=("qwen2.5:7b",))
        self.assertIn("ollama pull llama3", "\n".join(diagnostico.problemas(d)))
        self.assertIn("NÃO baixado", diagnostico.formatar(d))

    def test_python_muito_novo_aparece_no_diagnostico(self):
        d = self.coletar()
        d.python = "3.15.0"
        self.assertTrue(any("compilador C++" in p for p in diagnostico.problemas(d)))

    def test_banco_de_chats_existente_e_banco_corrompido(self):
        from rpgassistant.core.chats import GerenciadorDeChats
        g = GerenciadorDeChats.abrir()
        g.novo_chat()
        g.fechar()
        self.assertEqual(self.coletar().chats, 1)
        g2 = GerenciadorDeChats.abrir()
        g2.fechar()
        self.cfg.chats_db.write_bytes(b"isto nao e um banco " * 100)
        d = self.coletar()
        self.assertTrue(d.erro_banco)
        self.assertIn("banco de chats não abriu", "\n".join(diagnostico.problemas(d)))

    def test_formatar_nao_usa_emoji(self):
        saida = diagnostico.formatar(self.coletar())
        self.assertTrue(all(ord(c) < 0x2000 for c in saida), "a saída precisa caber em consoles sem UTF-8")


if __name__ == "__main__":
    unittest.main()