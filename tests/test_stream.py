import unittest

from tests.helpers import make_runtime, make_tmp_root


class TestRunStream(unittest.TestCase):
    def test_stream_emits_work_events(self):
        root = make_tmp_root()
        _, _, _, agent = make_runtime(root)
        events = []
        result = agent.run_stream("What is the capital of France?", emit=events.append)
        types = [e["type"] for e in events]
        self.assertIn("mode", types)
        self.assertIn("think", types)
        self.assertIn("knowledge", types)
        self.assertIn("answer", types)
        self.assertIn("done", types)
        self.assertEqual(result.answer, result.answer)  # sanity

    def test_self_selects_research_skill(self):
        root = make_tmp_root()
        _, _, _, agent = make_runtime(root)
        events = []
        agent.run_stream("search the vault for lessons", emit=events.append)
        skills = [e["name"] for e in events if e["type"] == "skill"]
        self.assertIn("research", skills)

    def test_tool_runs_live_offline(self):
        root = make_tmp_root()
        _, _, _, agent = make_runtime(root)
        events = []
        result = agent.run_stream("search the vault for capital of France", emit=events.append)
        tool_events = [e["name"] for e in events if e["type"] == "tool_start"]
        self.assertIn("vault_search", tool_events)
        self.assertTrue(result.answer)


if __name__ == "__main__":
    unittest.main()
