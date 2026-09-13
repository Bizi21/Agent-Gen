import unittest

from agent_gen.config import Config
from agent_gen.ui import _Runtime
from tests.helpers import make_tmp_root


class TestRuntime(unittest.TestCase):
    def setUp(self):
        self.root = make_tmp_root()
        self.config = Config.load(self.root)
        self.rt = _Runtime(self.config)

    def test_state_fields(self):
        st = self.rt.state()
        self.assertIn("graph", st)
        self.assertIn("noteList", st)
        self.assertIn("autonomy", st)
        self.assertIn("provider", st)
        self.assertIn("version", st)
        # seed note exists and has an excerpt + relpath
        self.assertTrue(any(n["relpath"].endswith("home.md") for n in st["noteList"]))
        home = next(n for n in st["noteList"] if n["relpath"].endswith("home.md"))
        self.assertTrue(home["excerpt"])

    def test_note_endpoint(self):
        data = self.rt.note("10-notes/home.md")
        self.assertEqual(data["title"], "Agent-Gen")
        self.assertIn("eval", data["body"])
        self.assertEqual(data["folder"], "10-notes")

    def test_note_missing(self):
        self.assertIn("error", self.rt.note("10-notes/nope.md"))

    def test_chat_stream_events(self):
        events = []
        self.rt.chat_stream("What is the capital of France?", emit=events.append)
        types = [e["type"] for e in events]
        self.assertIn("mode", types)
        self.assertIn("answer", types)
        self.assertIn("done", types)


if __name__ == "__main__":
    unittest.main()
