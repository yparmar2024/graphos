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
        action: Must be one of: 'store_finding', 'semantic_search', 'get_graph'.
        query: The search query for 'semantic_search'.
        content: The text summary to store for 'store_finding'. This will automatically create a node in the Knowledge Graph.
        node: An optional title or ID for the finding. If not provided, one will be generated.
    
    Returns:
        String confirming the action or returning search results.
    """
    init_memory()
    
    if action == "store_finding":
        if not content:
            return "Error: 'content' parameter is required for store_finding."
        if collection is None:
            return "Error: Vector DB not initialized."
        doc_id = node if node else f"finding_{collection.count() + 1}"
        collection.add(documents=[content], ids=[doc_id])
        
        # Automatically add it to the graph
        graph.add_node(doc_id, content=content)
        save_graph()
        
        return f"Successfully stored finding as {doc_id} in Vector DB and Knowledge Graph."
        
    elif action == "semantic_search":
        if graph is None:
            return "Graph not initialized."
        nodes = list(graph.nodes(data=True))
        edges = list(graph.edges(data=True))
        return json.dumps({"nodes": nodes, "edges": edges}, indent=2)
        
    else:
        return f"Error: Unknown action '{action}'."
