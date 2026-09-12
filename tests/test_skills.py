import unittest

from agent_gen.skills import load_skills, select_skills


SKILLS = [
    {"name": "research", "keywords": ["research", "search", "what is", "find"], "prompt": "r"},
    {"name": "coder", "keywords": ["code", "write", "python"], "prompt": "c"},
    {"name": "summarize", "keywords": ["summarize", "tldr"], "prompt": "s"},
]


class TestSkills(unittest.TestCase):
    def test_select_by_keyword(self):
        picked = select_skills("search the web for the capital of France", SKILLS)
        self.assertEqual(picked[0]["name"], "research")

    def test_no_match(self):
        self.assertEqual(select_skills("hello there", SKILLS), [])

    def test_rank_by_matches(self):
        picked = select_skills("search and find and what is this", SKILLS)
        self.assertEqual(picked[0]["name"], "research")
        self.assertEqual(len(picked), 1)


if __name__ == "__main__":
    unittest.main()
