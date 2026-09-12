import tempfile
import unittest
from pathlib import Path

from agent_gen.vault import Vault, slugify


class TestVault(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.vault = Vault(self.root)

    def test_structure_created(self):
        for folder in ("00-inbox", "10-notes", "90-meta"):
            self.assertTrue((self.root / folder).is_dir())

    def test_write_and_read_note(self):
        p = self.vault.write_note("Hello World", "The capital of France is [[Paris]]. #geography",
                                  folder="10-notes", tags=["geo"])
        self.assertTrue(p.exists())
        note = self.vault.read_note("10-notes/hello-world.md")
        self.assertIsNotNone(note)
        self.assertEqual(note.title, "Hello World")
        self.assertIn("Paris", note.links)
        self.assertIn("geography", note.tags)

    def test_search_finds_note(self):
        self.vault.write_note("France Facts", "Paris is the capital of France.", folder="10-notes")
        results = self.vault.search("capital of France")
        self.assertTrue(results)
        self.assertIn("Paris", results[0][0].body)

    def test_graph_has_nodes_and_edges(self):
        self.vault.write_note("A", "See [[B]]. #tag1", folder="10-notes")
        self.vault.write_note("B", "Linked from A.", folder="10-notes")
        g = self.vault.graph()
        titles = {n["title"] for n in g["nodes"]}
        self.assertIn("A", titles)
        self.assertIn("B", titles)
        self.assertGreaterEqual(len(g["edges"]), 1)

    def test_add_to_inbox(self):
        p = self.vault.add_to_inbox("hello capture", title="capture1")
        self.assertIn("00-inbox", str(p))


class TestSlugify(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(slugify("Hello, World!"), "hello-world")


if __name__ == "__main__":
    unittest.main()
