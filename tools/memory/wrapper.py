"""Run-scoped graph and vector memory with bounded retrieval."""

import hashlib
import json
import os
import threading
from pathlib import Path

import chromadb
import networkx as nx
from chromadb.config import Settings

MEMORY_DIR = Path(os.environ.get("MEMORY_DIR", "/app/run/memory"))
GRAPH_FILE = MEMORY_DIR / "graph.graphml"
chroma_client = None
collection = None
graph = None
_lock = threading.RLock()


def init_memory():
    global chroma_client, collection, graph
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    if collection is None:
        chroma_client = chromadb.PersistentClient(
            path=str(MEMORY_DIR / "chroma"),
            settings=Settings(anonymized_telemetry=False),
        )
        collection = chroma_client.get_or_create_collection(name="agent_findings")
    if graph is None:
        # Do not silently erase a corrupt graph.
        graph = nx.read_graphml(GRAPH_FILE) if GRAPH_FILE.exists() else nx.DiGraph()


def save_graph():
    temporary = GRAPH_FILE.with_suffix(".tmp")
    nx.write_graphml(graph, temporary)
    temporary.replace(GRAPH_FILE)


def store_findings(findings):
    """Upsert a scan's findings in one embedding batch and one graph checkpoint."""
    with _lock:
        init_memory()
        records = {}
        for finding in findings:
            content = finding["content"].strip()
            if not content:
                raise ValueError("Finding content cannot be empty")
            identifier = (
                finding.get("node")
                or "finding_" + hashlib.sha256(content.encode()).hexdigest()[:20]
            )
            records[identifier] = content
        if not records:
            return []
        collection.upsert(ids=list(records), documents=list(records.values()))
        for identifier, content in records.items():
            graph.add_node(identifier, content=content)
        save_graph()
        return list(records)


def execute(
    action: str,
    query: str = "",
    source: str = "",
    target: str = "",
    relation: str = "",
    content: str = "",
    node: str = "",
    attributes: str = "{}",
    limit: int = 10,
) -> str:
    """Manage run memory.

    Actions: store_finding (content, optional node), semantic_search (query, limit),
    get_graph (optional node for its neighborhood, limit), add_relation
    (source, target, relation, optional JSON attributes). Retrieval is bounded.
    """
    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")
    with _lock:
        if action == "store_finding":
            identifiers = store_findings([{"node": node, "content": content}])
            return json.dumps({"stored": identifiers})
        init_memory()
        if action == "semantic_search":
            if not query.strip():
                raise ValueError("query is required for semantic_search")
            count = collection.count()
            if not count:
                return json.dumps({"findings": []})
            result = collection.query(query_texts=[query], n_results=min(limit, count))
            return json.dumps(
                {
                    "findings": [
                        {"id": identifier, "content": text[:2000]}
                        for identifier, text in zip(result["ids"][0], result["documents"][0])
                    ]
                }
            )
        if action == "get_graph":
            if node and node not in graph:
                raise ValueError(f"Unknown node: {node}")
            candidates = (
                ([node] + sorted(set(graph.predecessors(node)) | set(graph.successors(node))))
                if node
                else list(graph.nodes)
            )
            selected = candidates[:limit]
            subgraph = graph.subgraph(selected)
            edges = list(subgraph.edges(data=True))
            return json.dumps(
                {
                    "nodes": [
                        {"id": key, "content": data.get("content", "")[:2000]}
                        for key, data in subgraph.nodes(data=True)
                    ],
                    "edges": edges[:limit],
                    "total_nodes": graph.number_of_nodes(),
                    "total_edges": graph.number_of_edges(),
                    "truncated": len(candidates) > limit or len(edges) > limit,
                }
            )
        if action == "add_relation":
            if not source or not target or not relation:
                raise ValueError("source, target and relation are required")
            if source not in graph or target not in graph:
                raise ValueError("Store both endpoint nodes before adding a relation")
            metadata = json.loads(attributes)
            if not isinstance(metadata, dict) or any(
                not isinstance(value, (str, int, float, bool)) for value in metadata.values()
            ):
                raise ValueError("attributes must be a JSON object of scalar values")
            metadata["relation"] = relation
            graph.add_edge(source, target, **metadata)
            save_graph()
            return json.dumps({"source": source, "target": target, **metadata})
        raise ValueError(f"Unknown memory action: {action}")
