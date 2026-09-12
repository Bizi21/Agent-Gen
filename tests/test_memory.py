import tempfile
import unittest
from pathlib import Path

from agent_gen.memory.store import Memory


class TestMemory(unittest.TestCase):
    def setUp(self):
        self.db = Path(tempfile.mkdtemp()) / "mem.db"
        self.mem = Memory(self.db)

    def tearDown(self):
        self.mem.close()

    def test_log_and_recent(self):
        self.mem.log("task", {"a": 1})
        self.mem.log("remember", {"text": "hi"})
        recent = self.mem.recent()
        self.assertGreaterEqual(len(recent), 2)
        self.assertEqual(recent[0]["kind"], "remember")

    def test_conversation(self):
        self.mem.add_message("s1", "user", "hello")
        self.mem.add_message("s1", "assistant", "hi")
        hist = self.mem.history("s1")
        self.assertEqual(len(hist), 2)
        self.assertEqual(hist[0], ("user", "hello"))
        self.assertIn("s1", self.mem.sessions())


if __name__ == "__main__":
    unittest.main()
