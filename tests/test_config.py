import unittest
from pathlib import Path

from agent_gen.config import Config, parse_env_file


class TestEnvParser(unittest.TestCase):
    def test_parse_basic(self):
        p = Path(__file__).with_name("_tmp.env")
        p.write_text("KEY1=value1\n# comment\nKEY2= hello world \nEMPTY=\n")
        try:
            got = parse_env_file(p)
        finally:
            p.unlink(missing_ok=True)
        self.assertEqual(got["KEY1"], "value1")
        self.assertEqual(got["KEY2"], "hello world")
        self.assertEqual(got.get("EMPTY"), "")

    def test_bool_int(self):
        c = Config(root=Path("/tmp"))
        self.assertEqual(c.max_steps, 0)


class TestConfigLoad(unittest.TestCase):
    def test_env_overrides_and_routing(self):
        root = Path(__import__("tempfile").mkdtemp())
        (root / "brain" / "config").mkdir(parents=True)
        (root / "brain" / "config" / "agent.json").write_text('{"limits": {"max_steps": 5}}')
        (root / ".env").write_text(
            "AGENT_GEN_PROVIDER=anthropic\n"
            "AGENT_GEN_MODEL_CHAT=openai/gpt-4o\n"
            "AGENT_GEN_MAX_STEPS=0\n"
            "ANTHROPIC_API_KEY=test-key\n"
            "AGENT_GEN_LANGUAGES=en,hi,fr\n"
        )
        c = Config.load(root)
        self.assertEqual(c.provider, "anthropic")
        self.assertEqual(c.route("chat"), ("openai", "gpt-4o"))
        self.assertEqual(c.max_steps, 0)  # env 0 overrides json 5
        self.assertEqual(c.provider_keys.get("anthropic"), "test-key")
        self.assertEqual(c.languages, ["en", "hi", "fr"])


if __name__ == "__main__":
    unittest.main()
