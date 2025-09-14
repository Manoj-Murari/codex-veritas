"""
The Semantic Indexer: The Code Librarian.

This module is responsible for building the semantic layer of our analysis.
It takes a structural code graph, extracts the meaningful code content for each
node (like function bodies), and then uses a sentence-transformer model to
create a dense vector embedding for each piece of content.

These embeddings are stored in a ChromaDB vector database, creating a powerful,
searchable index that allows for finding code based on conceptual similarity
rather than just keywords.
"""

import shutil
from pathlib import Path
import json
from typing import List, Dict, Any

import chromadb
from chromadb.utils import embedding_functions
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn

# --- Local Imports ---
from ..graph.core import CodeGraph

# --- Configuration ---
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
BATCH_SIZE = 100

# --- Helper function ---
def _prepare_code_chunks_from_graph(graph: CodeGraph, repo_path: Path) -> List[Dict[str, Any]]:
    """
    Reads the code_graph, gets the code for each relevant node,
    and prepares it for batch embedding.
    """
    print("   - Preparing code chunks from graph for embedding...")
    
    chunks_to_process = []
    
    for node_id, node_data in graph.graph.nodes(data=True):
        if node_data.get('type') in ['Function', 'Class', 'Method']:
            try:
                file_path = repo_path / node_data['file_path']
                
                # A more advanced implementation would use start/end lines to extract
                # the exact block. For now, we use the whole file for context.
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    code_string = f.read()

                if code_string:
                    chunks_to_process.append({
                        "id": node_id,
                        "code_string": code_string,
                        "file": node_data['file_path'],
                        "name": node_data['name'],
                        "type": node_data['type']
                    })
            except (FileNotFoundError, KeyError):
                print(f"     - ⚠️ Warning: Could not find file or data for node {node_id}. Skipping.")
                continue
    
    unique_chunks = {chunk['id']: chunk for chunk in chunks_to_process}
    final_chunks = list(unique_chunks.values())
    
    print(f"   - ✅ Prepared {len(final_chunks)} unique code chunks for embedding.")
    return final_chunks

# --- Main Execution Function ---
def build_semantic_layer(
    graph_path: Path, 
    repo_path: Path, 
    db_path: Path, 
    collection_name: str
):
    """Main function to run the semantic layer pipeline."""
    
    # --- ChromaDB Setup ---
    print("   - Initializing code-aware embedding model...")
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )

    if db_path.exists():
        print(f"   - 🗑️ Deleting old ChromaDB database at {db_path}.")
        shutil.rmtree(db_path)

    client = chromadb.PersistentClient(path=str(db_path))

    collection = client.create_collection(
        name=collection_name,
        embedding_function=sentence_transformer_ef,
        metadata={"hnsw:space": "cosine"}
    )
    print(f"   - ✨ Created new ChromaDB collection '{collection_name}'.")
    
    graph = CodeGraph()
    graph.load_from_json(graph_path)

    all_chunks = _prepare_code_chunks_from_graph(graph, repo_path)
    if not all_chunks:
        print("   - No code chunks to process. Exiting.")
        return

    print("   - 🔄 Processing and embedding code chunks...")
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
    ) as progress:
        task = progress.add_task("[green]Embedding...", total=len(all_chunks))
        
        for i in range(0, len(all_chunks), BATCH_SIZE):
            batch = all_chunks[i:i + BATCH_SIZE]
            
            ids_list = [chunk['id'] for chunk in batch]
            docs_list = [chunk['code_string'] for chunk in batch]
            meta_list = [
                {"file_path": chunk['file'], "name": chunk['name'], "type": chunk['type']} 
                for chunk in batch
            ]

            try:
                collection.add(
                    ids=ids_list,
                    documents=docs_list,
                    metadatas=meta_list
                )
                progress.update(task, advance=len(batch))
            except Exception as e:
                print(f"     - ❌ An error occurred during ChromaDB insertion: {e}")

    print(f"\n--- Vector database is now up-to-date at: {db_path} ---")

