import unittest

from agent_gen.config import Config
from agent_gen.gateway.base import Message
from agent_gen.gateway.mock import MockLLM
from agent_gen.gateway.registry import build_llm, resolve_llm


class TestMockLLM(unittest.TestCase):
    def test_echoes_context(self):
        llm = MockLLM()
        msg = Message(role="user", content="KNOWLEDGE:\nParis is the capital.\n\nTASK:\nwhat?")
        resp = llm.chat([msg])
        self.assertIn("Paris is the capital", resp.content)

    def test_no_context(self):
        llm = MockLLM()
        resp = llm.chat([Message(role="user", content="KNOWLEDGE:\n\n\nTASK:\nhello")])
        self.assertIn("don't know", resp.content)

    def test_embed_shape(self):
        llm = MockLLM()
        vecs = llm.embed(["hello", "world"])
        self.assertEqual(len(vecs), 2)
        self.assertEqual(len(vecs[0]), 32)


class TestRegistry(unittest.TestCase):
    def test_falls_back_to_mock_without_keys(self):
        config = Config.load()
        llm = resolve_llm("chat", config)
        self.assertIsInstance(llm, MockLLM)

    def test_build_unknown_provider_falls_back(self):
        config = Config.load()
        llm = build_llm("not-a-real-provider", "x", config)
        self.assertIsInstance(llm, MockLLM)


if __name__ == "__main__":
    unittest.main()
