# app/api/routes.py

import os
import json
import time
import pickle
from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from app.services.memory import MemoryStore
from app.services.vector_store import get_chroma_client, init_collection
from app.services.rag import (
    chunk_text,
    embed_chunks,
    embed_query,
    build_rag_prompt,
)
from app.services.auth import get_current_user  # our JWT dependency
from app.models.user import User                 # SQLAlchemy User model
from app.services.llm_providers import build_provider
from app.services.model_registry import (
    list_available_models,
    resolve_default_model,
    lookup_model,
)

router = APIRouter()
_memory_stores: dict[int, MemoryStore] = {}
CONTEXT_ENABLED = os.getenv("CONTEXT_ENABLED", "false").lower() == "true"

# ──────────────────────────────────────────────────────────────────────────────
# 1) Per‐user chat_history persistence
# ──────────────────────────────────────────────────────────────────────────────

CHAT_HISTORY_DIR = "chat_history"
os.makedirs(CHAT_HISTORY_DIR, exist_ok=True)

def _normalize_session_id(session_id: str | None) -> str:
    if not session_id:
        return "default"
    filtered = "".join(ch for ch in session_id if ch.isalnum() or ch in {"-", "_"})
    return filtered[:64] or "default"

def user_history_file(user_id: int, session_id: str) -> str:
    """
    Return the path for this user’s chat-history file for a session.
    """
    session_id = _normalize_session_id(session_id)
    user_dir = os.path.join(CHAT_HISTORY_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    return os.path.join(user_dir, f"{session_id}.json")

def _legacy_history_file(user_id: int) -> str:
    return os.path.join(CHAT_HISTORY_DIR, f"{user_id}.json")

def load_chat_history(user_id: int, session_id: str) -> tuple[List[dict], dict]:
    """
    Load chat history from disk for this user/session.
    Returns (messages, session_meta).
    """
    path = user_history_file(user_id, session_id)
    paths_to_try = [path]
    if _normalize_session_id(session_id) == "default":
        paths_to_try.append(_legacy_history_file(user_id))

    for candidate in paths_to_try:
        if os.path.exists(candidate):
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data, {}
                    if isinstance(data, dict):
                        messages = data.get("messages", [])
                        session_meta = data.get("session", {})
                        if isinstance(messages, list) and isinstance(session_meta, dict):
                            return messages, session_meta
            except Exception:
                pass
    return [], {}

def persist_chat_history(user_id: int, session_id: str, chat_history: List[dict], session_meta: dict):
    """
    Write this user’s chat_history and session metadata to disk.
    """
    path = user_history_file(user_id, session_id)
    payload = {"messages": chat_history, "session": session_meta}
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error writing chat history for user {user_id}: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# 2) RAG endpoints (per‐user Chroma collections)
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/api/models")
def list_models(current_user: User = Depends(get_current_user)):
    """
    Return the list of enabled models for this deployment.
    """
    models = [
        {
            "provider": spec.provider,
            "model": spec.model,
            "display_name": spec.display_name,
        }
        for spec in list_available_models()
    ]
    default_spec = resolve_default_model()
    default_payload = None
    if default_spec:
        default_payload = {
            "provider": default_spec.provider,
            "model": default_spec.model,
        }
    return {"models": models, "default": default_payload}

@router.get("/rag/health")
def rag_health(current_user: User = Depends(get_current_user)):
    """
    Verify that the per-user Chroma collection can be opened/created.
    """
    try:
        collection_name = f"documents_{current_user.id}"
        client = get_chroma_client()
        _ = init_collection(collection_name)
        return {"status": "chroma ok", "collection": collection_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chroma health check failed: {e}")


@router.post("/rag/ingest")
async def ingest(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Ingest uploaded files into this user’s Chroma collection.
    """
    collection_name = f"documents_{current_user.id}"
    all_texts: List[str] = []
    all_ids: List[str] = []
    all_metadatas: List[dict] = []

    for upload in files:
        raw = await upload.read()
        text = raw.decode("utf-8", errors="ignore")
        chunks = chunk_text(text)

        base_name = upload.filename or "unknown"
        for idx, chunk in enumerate(chunks):
            # Prefix each ID with user_id so it can’t collide with others
            chunk_id = f"{current_user.id}__{base_name}_chunk{idx}"
            all_ids.append(chunk_id)
            all_texts.append(chunk)
            all_metadatas.append({
                "source_file": base_name,
                "chunk_index": idx,
                "user_id": current_user.id,
            })

    embeddings = embed_chunks(all_texts)

    collection = init_collection(collection_name)
    collection.add(
        ids=all_ids,
        embeddings=embeddings,
        metadatas=all_metadatas,
        documents=all_texts,
    )
    return {
        "message": f"Ingested {len(all_ids)} chunks into Chroma for user {current_user.id}."
    }


class RagAskRequest(BaseModel):
    query: str
    top_k: int = 5
    provider: str | None = None
    model: str | None = None

@router.post("/rag/ask")
async def ask(
    req: RagAskRequest,
    current_user: User = Depends(get_current_user),
):
    """
    1) Embed the query and retrieve top_k chunks from this user’s Chroma collection.
    2) Build a single “blended” prompt.
    3) Call ChatGPT once to get a combined answer.
    4) Return that answer plus the source chunks.
    """
    collection_name = f"documents_{current_user.id}"

    # ─── 1) Time the embedding step ─────────────────────────────────────────────
    t0 = time.time()
    q_embedding = embed_query(req.query)
    embed_duration = time.time() - t0

    # ─── 2) Time the Chroma query step ─────────────────────────────────────────
    collection = init_collection(collection_name)
    t1 = time.time()
    results = collection.query(
        query_embeddings=[q_embedding],
        n_results=req.top_k
    )
    chroma_duration = time.time() - t1

    chunks = results["documents"][0]
    metadatas = results["metadatas"][0]

    # ─── 3) Build the blended prompt (no need to time string concatenation) ────
    prompt_text = build_rag_prompt(chunks, req.query)

    # ─── 4) Time the GPT-4 Turbo API call ───────────────────────────────────────
    selected_provider = req.provider.lower() if req.provider else None
    selected_model = req.model
    if selected_provider and selected_model:
        if not lookup_model(selected_provider, selected_model):
            raise HTTPException(status_code=400, detail="Selected model is not available")
    elif selected_provider or selected_model:
        raise HTTPException(status_code=400, detail="Both provider and model are required")
    else:
        default_spec = resolve_default_model()
        if not default_spec:
            raise HTTPException(status_code=500, detail="No models are configured")
        selected_provider = default_spec.provider
        selected_model = default_spec.model

    try:
        provider = build_provider(selected_provider)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    t2 = time.time()
    blended_answer = provider.chat(
        messages=[{"role": "user", "content": prompt_text}],
        model=selected_model,
        temperature=0.0,
    )
    gpt_duration = time.time() - t2

    # ─── 5) Log all three durations ─────────────────────────────────────────────
    print(f"[timing] embed: {embed_duration:.3f}s  chroma: {chroma_duration:.3f}s  gpt: {gpt_duration:.3f}s")

    # ─── 6) Prepare and return the response as before ──────────────────────────
    sources = [
        {
            "id": results["ids"][0][i],
            "metadata": metadatas[i],
            "chunk": chunks[i]
        }
        for i in range(len(chunks))
    ]

    return {
        "query": req.query,
        "answer": blended_answer,
        "provider": selected_provider,
        "model": selected_model,
        "sources": sources
    }


# ──────────────────────────────────────────────────────────────────────────────
# 3) Memory‐based endpoints, now per‐user
# ──────────────────────────────────────────────────────────────────────────────

# Directory for per‐user memory files
MEMORY_DIR = "memory_store"
os.makedirs(MEMORY_DIR, exist_ok=True)

def get_memory_store(user_id: int) -> MemoryStore:
    store = _memory_stores.get(user_id)
    if store is None:
        store = MemoryStore()
        _memory_stores[user_id] = store
    return store

def user_memory_file(user_id: int) -> str:
    """
    Returns the path for a given user’s memory pickle file.
    """
    return os.path.join(MEMORY_DIR, f"memory_{user_id}.pkl")

def load_memory_for_user(user_id: int, store: MemoryStore):
    """
    Load memory_store.texts & memory_store.embeddings from disk for this user.
    If no file exists, leave memory_store empty.
    """
    path = user_memory_file(user_id)
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                store.texts, store.embeddings = pickle.load(f)
        except Exception:
            store.texts, store.embeddings = [], []
    else:
        store.texts, store.embeddings = [], []

def persist_memory_for_user(user_id: int, store: MemoryStore):
    """
    Write this user’s memory_store.texts & embeddings to disk.
    """
    path = user_memory_file(user_id)
    try:
        with open(path, "wb") as f:
            pickle.dump((store.texts, store.embeddings), f)
    except Exception as e:
        print(f"Error persisting memory for user {user_id}: {e}")

class AskRequest(BaseModel):
    query: str

@router.post("/ask")
async def ask_memory(
    req: AskRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve from this user’s MemoryStore and run a memory‐only query.
    """
    # 1) Load this user’s memory from disk into memory_store
    store = get_memory_store(current_user.id)
    load_memory_for_user(current_user.id, store)

    # 2) Perform retrieval over memory_store
    memory_results = store.query(req.query, top_k=3)
    memory_context = "\n---\n".join(memory_results)

    enriched_query = (
        f"Answer the question using memory context:\n{memory_context}\n\nQ: {req.query}"
    )

    default_spec = resolve_default_model()
    if not default_spec:
        raise HTTPException(status_code=500, detail="No models are configured")
    try:
        provider = build_provider(default_spec.provider)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    answer = provider.chat(
        messages=[{"role": "user", "content": enriched_query}],
        model=default_spec.model,
        temperature=0.0,
    )
    return {"answer": answer, "provider": default_spec.provider, "model": default_spec.model}

@router.post("/upload")
async def upload_memory(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a text or PDF and add to this user’s MemoryStore.
    """
    store = get_memory_store(current_user.id)
    load_memory_for_user(current_user.id, store)

    if file.filename.endswith(".pdf"):
        from PyPDF2 import PdfReader  # local import
        pdf_reader = PdfReader(file.file)
        text = "\n".join(page.extract_text() or "" for page in pdf_reader.pages)
    else:
        contents = await file.read()
        text = contents.decode("utf-8", errors="ignore")

    store.add([text])
    persist_memory_for_user(current_user.id, store)

    return {"status": "File processed and added to your memory"}

@router.get("/memory")
async def memory_debug(
    current_user: User = Depends(get_current_user),
):
    """
    Simple HTML preview of the first few memory entries for this user.
    """
    store = get_memory_store(current_user.id)
    load_memory_for_user(current_user.id, store)
    html = "".join(f"<p>{i+1}. {entry[:300]}...</p>"
                   for i, entry in enumerate(store.texts[:3]))
    return HTMLResponse(content=f"<html><body><h2>Your Memory Preview</h2>{html}</body></html>")

@router.get("/api/memory")
async def get_memory(
    offset: int = 0,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
):
    """
    Return a paginated slice of this user’s memories as JSON.
    """
    store = get_memory_store(current_user.id)
    load_memory_for_user(current_user.id, store)
    preview = store.texts[offset : offset + limit]
    return JSONResponse(content={"memory": preview})

@router.post("/remember")
async def remember(
    item: AskRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Add a single text string to this user’s memory.
    """
    store = get_memory_store(current_user.id)
    load_memory_for_user(current_user.id, store)
    store.add([item.query])
    persist_memory_for_user(current_user.id, store)
    return {"status": "Remembered"}

@router.delete("/api/memory/{index}")
async def delete_memory(
    index: int,
    current_user: User = Depends(get_current_user),
):
    """
    Delete a single memory entry by index from this user’s store.
    """
    store = get_memory_store(current_user.id)
    load_memory_for_user(current_user.id, store)
    try:
        del store.texts[index]
        del store.embeddings[index]
        persist_memory_for_user(current_user.id, store)
        return {"status": f"Deleted memory at index {index}"}
    except IndexError:
        raise HTTPException(status_code=404, detail="Memory index not found")

@router.delete("/api/memory")
async def clear_memory(
    current_user: User = Depends(get_current_user),
):
    """
    Clear all memories for this user.
    """
    store = get_memory_store(current_user.id)
    store.texts.clear()
    store.embeddings.clear()
    persist_memory_for_user(current_user.id, store)
    return {"status": "All memory cleared"}


# ──────────────────────────────────────────────────────────────────────────────
# 4) Chat endpoints with persistence (UPDATED to include MemoryStore context)
# ──────────────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    message: str
    session_id: str | None = None
    provider: str | None = None
    model: str | None = None

@router.get("/api/history")
def get_history(
    session_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    """
    Load and return this user’s persisted chat history from disk.
    """
    session_id = _normalize_session_id(session_id)
    messages, session_meta = load_chat_history(current_user.id, session_id)
    return {"messages": messages, "session": session_meta}


@router.post("/api/chat")
def post_message(
    msg: ChatMessage,
    current_user: User = Depends(get_current_user),
):
    """
    1) Append the user’s message to their chat history file,
       then generate an assistant reply using BOTH MemoryStore and RAG.
    2) Append the assistant message, persist again, and return it.
    """
    session_id = _normalize_session_id(msg.session_id)

    # 1) Load existing history
    chat_history, session_meta = load_chat_history(current_user.id, session_id)

    # 2) Append user message + persist
    chat_history.append({"role": "user", "content": msg.message})
    persist_chat_history(current_user.id, session_id, chat_history, session_meta)

    if CONTEXT_ENABLED:
        # ───────────────────────────
        # 2A) Load this user's MemoryStore from disk
        # ───────────────────────────
        store = get_memory_store(current_user.id)
        load_memory_for_user(current_user.id, store)

        # 2B) Retrieve top‐3 memory chunks (strings) relevant to this query
        memory_results = store.query(msg.message, top_k=3)
        memory_context = "\n--- Memory Context ---\n".join(memory_results) if memory_results else ""

        # ───────────────────────────
        # 2C) Retrieve top‐3 documents from this user's Chroma collection
        # ───────────────────────────
        q_embedding = embed_query(msg.message)
        collection_name = f"documents_{current_user.id}"
        collection = init_collection(collection_name)
        results = collection.query(query_embeddings=[q_embedding], n_results=3)

        chroma_chunks = results["documents"][0]
        chroma_context = "\n--- Retrieved Context ---\n".join(chroma_chunks) if chroma_chunks else ""

        # ───────────────────────────
        # 2D) Build a single blended prompt string
        # ───────────────────────────
        if memory_context and chroma_context:
            combined_context = f"{memory_context}\n---\n{chroma_context}"
        else:
            combined_context = memory_context or chroma_context

        if combined_context:
            prompt_text = (
                "You are a helpful assistant. Below is some context that has been "
                "retrieved from the user’s prior “memory” and from uploaded documents:\n\n"
                f"{combined_context}\n\n"
                f"User’s Question: {msg.message}\n"
                "Assistant’s Answer:"
            )
        else:
            prompt_text = (
                "You are a helpful assistant. Answer as best you can.\n\n"
                f"User’s Question: {msg.message}\n"
                "Assistant’s Answer:"
            )
    else:
        prompt_text = (
            "You are a helpful assistant. Answer as best you can.\n\n"
            f"User’s Question: {msg.message}\n"
            "Assistant’s Answer:"
        )

    # ───────────────────────────
    # 3) Single ChatGPT call
    # ───────────────────────────
    selected_provider = msg.provider.lower() if msg.provider else None
    selected_model = msg.model
    if selected_provider and selected_model:
        if not lookup_model(selected_provider, selected_model):
            raise HTTPException(status_code=400, detail="Selected model is not available")
        session_meta["provider"] = selected_provider
        session_meta["model"] = selected_model
    elif selected_provider or selected_model:
        raise HTTPException(status_code=400, detail="Both provider and model are required")
    else:
        if "provider" not in session_meta or "model" not in session_meta:
            default_spec = resolve_default_model()
            if not default_spec:
                raise HTTPException(status_code=500, detail="No models are configured")
            session_meta["provider"] = default_spec.provider
            session_meta["model"] = default_spec.model

    if not lookup_model(session_meta["provider"], session_meta["model"]):
        default_spec = resolve_default_model()
        if not default_spec:
            raise HTTPException(status_code=500, detail="No models are configured")
        session_meta["provider"] = default_spec.provider
        session_meta["model"] = default_spec.model

    persist_chat_history(current_user.id, session_id, chat_history, session_meta)

    try:
        provider = build_provider(session_meta["provider"])
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    try:
        reply_text = provider.chat(
            messages=[{"role": "user", "content": prompt_text}],
            model=session_meta["model"],
            temperature=0.0,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "provider": session_meta.get("provider"),
                "model": session_meta.get("model"),
                "error": str(exc),
            },
        )

    # 4) Append assistant message + persist again
    chat_history.append(
        {
            "role": "assistant",
            "content": reply_text,
            "provider": session_meta.get("provider"),
            "model": session_meta.get("model"),
        }
    )
    persist_chat_history(current_user.id, session_id, chat_history, session_meta)

    return {"reply": reply_text, "session": session_meta, "session_id": session_id}
