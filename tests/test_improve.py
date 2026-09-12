import unittest

from agent_gen.evals.harness import run_suite, scorecard
from agent_gen.evals.suite import DEFAULT_SUITE
from agent_gen.improve.loop import run_improve
from agent_gen.vault import Vault

from tests.helpers import make_runtime, make_tmp_root


class TestImproveLoop(unittest.TestCase):
    def test_improve_learns_until_all_pass(self):
        root = make_tmp_root()
        config, vault, _, agent = make_runtime(root)

        report = run_improve(
            agent, DEFAULT_SUITE, config, vault,
            config.brain_dir / "prompt" / "system.md",
            max_rounds=4,
        )

        card = report["final_scorecard"]
        self.assertIsNotNone(card)
        self.assertEqual(card.passed, card.total)
        # the loop should have committed at least once
        self.assertTrue(report["commits"])
        # lesson notes should now exist in the vault
        lessons = list((vault.path / "10-notes").glob("lesson-*.md"))
        self.assertGreaterEqual(len(lessons), 1)

    def test_improve_is_idempotent(self):
        root = make_tmp_root()
        config, vault, _, agent = make_runtime(root)

        first = run_improve(agent, DEFAULT_SUITE, config, vault,
                            config.brain_dir / "prompt" / "system.md", max_rounds=4)
        self.assertEqual(first["final_scorecard"].passed, first["final_scorecard"].total)

        second = run_improve(agent, DEFAULT_SUITE, config, vault,
                             config.brain_dir / "prompt" / "system.md", max_rounds=2)
        # no failures left -> nothing new committed
        self.assertEqual(second["commits"], [])
        self.assertEqual(second["final_scorecard"].passed, second["final_scorecard"].total)


if __name__ == "__main__":
    unittest.main()
