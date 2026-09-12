import unittest

from agent_gen.evals.graders import grade
from agent_gen.evals.harness import run_suite, scorecard
from agent_gen.evals.suite import DEFAULT_SUITE, Task


class TestGraders(unittest.TestCase):
    def test_contains(self):
        t = Task("x", "facts", "q", "Paris", "contains")
        ok, score, _ = grade(t, "The capital is Paris.")
        self.assertTrue(ok)
        self.assertEqual(score, 1.0)

    def test_exact(self):
        t = Task("x", "facts", "q", "Paris", "exact")
        self.assertTrue(grade(t, "Paris")[0])
        self.assertFalse(grade(t, "The capital is Paris")[0])

    def test_regex(self):
        t = Task("x", "facts", "q", r"\d+", "regex")
        self.assertTrue(grade(t, "There are 42 apples")[0])


class TestSuite(unittest.TestCase):
    def test_default_suite_has_mixed_results_offline(self):
        from tests.helpers import make_runtime, make_tmp_root
        root = make_tmp_root()
        _, _, _, agent = make_runtime(root)
        results = run_suite(agent, DEFAULT_SUITE)
        card = scorecard(results)
        # some tasks pass via the seed note; others fail and are learnable
        self.assertGreater(card.passed, 0)
        self.assertLess(card.passed, card.total)
        self.assertTrue(card.failures)


if __name__ == "__main__":
    unittest.main()
