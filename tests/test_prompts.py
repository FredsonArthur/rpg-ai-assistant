import string
import unittest

from rpgassistant.services import prompts


def campos(template: str) -> list:
    return sorted({nome for _, nome, _, _ in string.Formatter().parse(template) if nome})


class PromptsTest(unittest.TestCase):
    def test_placeholders_de_cada_prompt(self):
        esperados = {
            "SYSTEM_PROMPT": ["context"],
            "LIVROS_PROMPT": ["context"],
            "MASTER_PROMPT": ["character", "context", "dados", "estado", "scenario"],
            "PLAYER_PROMPT": ["archetype", "character", "dados"],
            "FEEDBACK_PROMPT": ["history"],
            "REWRITE_PROMPT": ["history", "question"],
        }
        for nome, esperado in esperados.items():
            with self.subTest(prompt=nome):
                self.assertEqual(campos(getattr(prompts, nome)), esperado)

    def test_assistente_ignora_argumento_extra(self):
        texto = prompts.SYSTEM_PROMPT.format(context="X", question="ignorada")
        self.assertIn("<contexto>\nX\n</contexto>", texto)

    def test_exemplo_do_jogador_termina_corretamente(self):
        self.assertTrue(prompts.PLAYER_PROMPT.rstrip().endswith('dele?"'))

    def test_prompt_dos_livros_manda_responder_com_a_sentinela(self):
        from rpgassistant.core import policy
        self.assertIn(policy.SENTINELA, prompts.LIVROS_PROMPT)
        self.assertIn("SOMENTE", prompts.LIVROS_PROMPT)
        self.assertNotIn("conhecimento geral", prompts.LIVROS_PROMPT)

    def test_arquetipos(self):
        self.assertEqual(list(prompts.ARCHETYPES), ["Iniciante", "Tático", "Roleplay"])


if __name__ == "__main__":
    unittest.main()