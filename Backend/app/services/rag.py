# app/services/rag.py

import re
import os
from typing import List, Optional
from openai import OpenAI

# ──────────────────────────────────────────────────────────────────────────────
# 1) Basic text‐chunking logic (approximate 500-word chunks with 50-word overlap)
# ──────────────────────────────────────────────────────────────────────────────

CHUNK_SIZE = 500
OVERLAP_SIZE = 50

def chunk_text(text: str) -> list[str]:
    """
    Split a large string into smaller chunks of ~CHUNK_SIZE words,
    overlapping by ~OVERLAP_SIZE words between consecutive chunks.
    """
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    words = text.split(" ")
    if len(words) <= CHUNK_SIZE:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + CHUNK_SIZE, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        # Move start forward but leave overlap
        start += CHUNK_SIZE - OVERLAP_SIZE

    return chunks


# ──────────────────────────────────────────────────────────────────────────────
# 2) OpenAI embedding calls via the new v1 Python client (synchronous)
# ──────────────────────────────────────────────────────────────────────────────

# Instantiate a single OpenAI client for use across calls
_client: Optional[OpenAI] = None

def get_openai_client() -> OpenAI:
    """
    Return a singleton OpenAI client (v1 interface).
    """
    global _client
    if _client is None:
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        _client = OpenAI(api_key=openai_api_key)
    return _client

EMBED_MODEL = "text-embedding-ada-002"


def embed_chunks(chunks: List[str]) -> List[list[float]]:
    """
    Given a list of text chunks, call the OpenAI Embeddings API (synchronously)
    and return a list of embedding vectors (each a list of floats).
    """
    client = get_openai_client()
    embeddings: list[list[float]] = []
    batch_size = 50  # send up to 50 chunks per API call

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        resp = client.embeddings.create(
            input=batch,
            model=EMBED_MODEL
        )
        # resp.data is a list of objects, each has a .embedding attribute
        for item in resp.data:
            embeddings.append(item.embedding)

    return embeddings


def embed_query(query: str) -> list[float]:
    """
    Embed a single query string (used at search time) synchronously.
    """
    client = get_openai_client()
    resp = client.embeddings.create(
        input=[query],
        model=EMBED_MODEL
    )
    return resp.data[0].embedding

def build_rag_prompt(chunks: list[str], query: str) -> str:
    """
    Assemble a single prompt that:
      1) Gives the model retrieved context excerpts.
      2) Instructs it to use that context first to answer.
      3) Encourages it to supplement from its own knowledge where the context is incomplete.
      4) Does NOT produce any “context missing” boilerplate in the final answer.

    You will pass this entire string as one "user" message to ChatGPT.
    """
    # 1) Join all chunks with clear separators
    context_block = "\n\n--- Retrieved Context ---\n\n".join(chunks)

    prompt = (
        "You are a helpful assistant. Use the context excerpts below to answer the user’s question as completely as possible.\n"
        "If some details aren’t covered by the context, you may fill in from your own knowledge to make a thorough, coherent answer.\n\n"
        "=== Context ===\n"
        f"{context_block}\n\n"
        "=== End Context ===\n\n"
        f"User’s Question: {query}\n"
        "Assistant’s Answer:"
    )
    return prompt
