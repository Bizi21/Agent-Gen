import unittest

from tests.helpers import make_runtime, make_tmp_root


class TestAgent(unittest.TestCase):
    def test_agent_answers_from_seed_note(self):
        root = make_tmp_root()
        try:
            _, _, _, agent = make_runtime(root)
            result = agent.run("What is the eval command in Agent-Gen?")
            self.assertIn("/eval", result.answer)
        finally:
            pass

    def test_agent_says_unknown_without_knowledge(self):
        root = make_tmp_root()
        _, _, _, agent = make_runtime(root)
        result = agent.run("What is the capital of France?")
        self.assertNotIn("Paris", result.answer)


if __name__ == "__main__":
    unittest.main()
