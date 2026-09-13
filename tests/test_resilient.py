import unittest

from agent_gen.gateway.base import LLM, Message
from agent_gen.gateway.mock import MockLLM
from agent_gen.gateway.resilient import ResilientLLM


class BoomLLM(LLM):
    name = "boom"

    def chat(self, messages, tools=None):
        raise RuntimeError("network down")

    def complete(self, prompt):
        raise RuntimeError("network down")


class TestResilient(unittest.TestCase):
    def test_falls_back_on_error(self):
        llm = ResilientLLM(BoomLLM())
        self.assertFalse(llm.degraded)
        resp = llm.chat([Message(role="user", content="hello")])
        self.assertTrue(llm.degraded)
        self.assertIsNotNone(llm.last_error)
        # fallback is the mock: echoes knowledge / answers something
        self.assertIsInstance(resp.content, str)

    def test_primary_used_when_healthy(self):
        llm = ResilientLLM(MockLLM())
        resp = llm.chat([Message(role="user", content="KNOWLEDGE:\nParis\n\nTASK:\nwhere?")])
        self.assertFalse(llm.degraded)
        self.assertIn("Paris", resp.content)

    def test_name_propagates(self):
        self.assertEqual(ResilientLLM(BoomLLM()).name, "boom")


if __name__ == "__main__":
    unittest.main()
