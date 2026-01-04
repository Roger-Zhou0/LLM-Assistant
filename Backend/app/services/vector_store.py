# app/services/vector_store.py

import os
import chromadb
from chromadb.api.models.Collection import Collection
from typing import Optional

# ──────────────────────────────────────────────────────────────────────────────
# Use the new PersistentClient so Chroma stores data under ./chromadb
# ──────────────────────────────────────────────────────────────────────────────

_chroma_client: Optional[chromadb.PersistentClient] = None


def get_chroma_client() -> chromadb.PersistentClient:
    """
    Returns a singleton PersistentClient that persists vectors to ./chromadb/.
    """
    global _chroma_client
    if _chroma_client is None:
        # Ensure the directory exists
        os.makedirs("./chromadb", exist_ok=True)
        # persistent client will store its database files under the given path
        _chroma_client = chromadb.PersistentClient(path="./chromadb")
    return _chroma_client


def init_collection(collection_name: str) -> Collection:
    """
    Get (or create) a named Chroma collection. 
    We'll store our document chunks in a collection called "documents".
    """
    client = get_chroma_client()
    return client.get_or_create_collection(name=collection_name)
