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


class TestMockToolDirectives(unittest.TestCase):
    def _tools(self):
        return [{"name": "vault_search"}, {"name": "list_dir"}, {"name": "ingest_url"}]

    def test_search_triggers_tool(self):
        llm = MockLLM()
        resp = llm.chat([Message(role="user", content="search the vault for Paris")],
                        tools=self._tools())
        self.assertTrue(resp.tool_calls)
        self.assertEqual(resp.tool_calls[0].name, "vault_search")

    def test_plain_question_does_not_trigger_tool(self):
        llm = MockLLM()
        resp = llm.chat([Message(role="user", content="What is the capital of France?")],
                        tools=self._tools())
        self.assertFalse(resp.tool_calls)

    def test_ingest_url_triggers_tool(self):
        llm = MockLLM()
        resp = llm.chat([Message(role="user", content="ingest https://example.com please")],
                        tools=self._tools())
        self.assertTrue(resp.tool_calls)
        self.assertEqual(resp.tool_calls[0].name, "ingest_url")

    def test_tool_result_is_answered(self):
        llm = MockLLM()
        resp = llm.chat([Message(role="tool", content="RESULT-XYZ", tool_call_id="1")],
                        tools=self._tools())
        self.assertIn("RESULT-XYZ", resp.content)
        self.assertFalse(resp.tool_calls)


if __name__ == "__main__":
    unittest.main()
