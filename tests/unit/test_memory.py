import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import networkx as nx

from tools.memory import wrapper as memory


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.collection = MagicMock()
        self.collection.count.return_value = 2
        for name, value in {
            "MEMORY_DIR": Path(self.directory.name),
            "GRAPH_FILE": Path(self.directory.name) / "graph.graphml",
            "collection": self.collection,
            "graph": nx.DiGraph(),
        }.items():
            patcher = patch.object(memory, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_batch_upsert_deduplicates_and_reloads_graph(self):
        ids = memory.store_findings([{"content": "Port 80 open"}] * 2)
        self.assertEqual(len(ids), 1)
        self.collection.upsert.assert_called_once()
        self.assertEqual(len(memory.graph), 1)
        memory.graph = None
        memory.init_memory()
        self.assertEqual(memory.graph.nodes[ids[0]]["content"], "Port 80 open")
        memory.store_findings([{"node": ids[0], "content": "Port 80 runs HTTP"}])
        self.assertEqual(len(memory.graph), 1)
        self.assertEqual(memory.graph.nodes[ids[0]]["content"], "Port 80 runs HTTP")

    def test_semantic_search_uses_query_and_bounds_results(self):
        self.collection.query.return_value = {"ids": [["admin"]], "documents": [["Admin endpoint"]]}
        result = json.loads(memory.execute("semantic_search", query="admin", limit=3))
        self.collection.query.assert_called_once_with(query_texts=["admin"], n_results=2)
        self.assertEqual(result["findings"][0]["id"], "admin")

    def test_empty_search_and_invalid_actions(self):
        self.collection.count.return_value = 0
        self.assertEqual(
            json.loads(memory.execute("semantic_search", query="admin")), {"findings": []}
        )
        for arguments in (
            {"action": "unknown"},
            {"action": "semantic_search"},
            {"action": "get_graph", "limit": 100},
        ):
            with self.assertRaises(ValueError):
                memory.execute(**arguments)

    def test_relation_and_bounded_graph(self):
        memory.store_findings(
            [
                {"node": "host", "content": "Target host"},
                {"node": "port", "content": "HTTP service"},
            ]
        )
        memory.execute("add_relation", source="host", target="port", relation="exposes")
        result = json.loads(memory.execute("get_graph", node="host", limit=1))
        self.assertTrue(result["truncated"])
        self.assertEqual(result["total_edges"], 1)
        self.assertEqual(len(result["nodes"]), 1)
        self.assertEqual(memory.graph.edges["host", "port"]["relation"], "exposes")

    def test_corrupt_graph_is_not_silently_replaced(self):
        memory.GRAPH_FILE.write_text("broken")
        memory.graph = None
        with self.assertRaises(Exception):
            memory.init_memory()
        self.assertEqual(memory.GRAPH_FILE.read_text(), "broken")
