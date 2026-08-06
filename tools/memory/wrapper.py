# tools/memory/wrapper.py
import os
import json
from typing import Optional
import networkx as nx
import chromadb
from chromadb.config import Settings

# To prevent ChromaDB telemetry/warnings from polluting stdout
os.environ["CHROMA_TELEMETRY_IMPL"] = "None"

MEMORY_DIR = "/app/run/memory"
GRAPH_FILE = os.path.join(MEMORY_DIR, "graph.graphml")

# Global clients (lazy loaded to prevent startup crashes if dir doesn't exist yet)
chroma_client = None
collection = None
graph = None

def init_memory():
    global chroma_client, collection, graph
    if not os.path.exists(MEMORY_DIR):
        try:
            os.makedirs(MEMORY_DIR, exist_ok=True)
        except Exception:
            pass # Failsafe if running locally without mount
            
    if chroma_client is None:
        try:
            # Initialize persistent local vector DB
            chroma_client = chromadb.PersistentClient(
                path=os.path.join(MEMORY_DIR, "chroma"), 
                settings=Settings(anonymized_telemetry=False)
            )
            collection = chroma_client.get_or_create_collection(name="agent_findings")
        except Exception as e:
            print(f"Failed to init ChromaDB: {e}")
            
    if graph is None:
        if os.path.exists(GRAPH_FILE):
            try:
                graph = nx.read_graphml(GRAPH_FILE)
            except:
                graph = nx.DiGraph()
        else:
            graph = nx.DiGraph()

def save_graph():
    if graph is not None:
        try:
            nx.write_graphml(graph, GRAPH_FILE)
        except Exception as e:
            print(f"Failed to save graph: {e}")

def execute(
    action: str,
    query: str = "",
    source: str = "",
    target: str = "",
    relation: str = "",
    content: str = "",
    node: str = "",
    attributes: str = "{}"
) -> str:
    """
    Manages the agent's Vector Database and Knowledge Graph memory.
    
    Args:
        action: Must be one of: 'store_finding', 'semantic_search', 'add_node', 'add_relationship', 'get_graph'.
        query: The search query for 'semantic_search'.
        content: The text summary to store for 'store_finding'.
        node: The node ID for 'add_node'.
        source: The source node ID for 'add_relationship'.
        target: The target node ID for 'add_relationship'.
        relation: The relationship label for 'add_relationship'.
        attributes: JSON string of key/value pairs to attach to a node or relationship.
    
    Returns:
        String confirming the action or returning search results.
    """
    init_memory()
    
    if action == "store_finding":
        if not content:
            return "Error: 'content' parameter is required for store_finding."
        if collection is None:
            return "Error: Vector DB not initialized."
        doc_id = f"finding_{collection.count() + 1}"
        collection.add(documents=[content], ids=[doc_id])
        return f"Successfully stored finding as {doc_id} in Vector DB."
        
    elif action == "semantic_search":
        if not query:
            return "Error: 'query' parameter is required for semantic_search."
        if collection is None:
            return "Error: Vector DB not initialized."
        
        # Guard against querying an empty database
        if collection.count() == 0:
            return "Vector DB is currently empty."
            
        results = collection.query(query_texts=[query], n_results=3)
        if not results.get('documents') or not results['documents'][0]:
            return "No relevant findings found."
        formatted_results = "\n\n".join(results['documents'][0])
        return f"Top semantic search results:\n{formatted_results}"
        
    elif action == "add_node":
        if not node:
            return "Error: 'node' parameter is required for add_node."
        try:
            attrs = json.loads(attributes)
        except:
            attrs = {}
        graph.add_node(node, **attrs)
        save_graph()
        return f"Successfully added node: {node}"
        
    elif action == "add_relationship":
        if not source or not target or not relation:
            return "Error: 'source', 'target', and 'relation' are required for add_relationship."
        try:
            attrs = json.loads(attributes)
        except:
            attrs = {}
        graph.add_edge(source, target, label=relation, **attrs)
        save_graph()
        return f"Successfully added relationship: {source} -[{relation}]-> {target}"
        
    elif action == "get_graph":
        if graph is None:
            return "Graph not initialized."
        nodes = list(graph.nodes(data=True))
        edges = list(graph.edges(data=True))
        return json.dumps({"nodes": nodes, "edges": edges}, indent=2)
        
    else:
        return f"Error: Unknown action '{action}'."
