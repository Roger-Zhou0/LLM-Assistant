from dotenv import load_dotenv
load_dotenv()

import openai
from openai import OpenAI

import os
os.environ["STREAMLIT_WATCHER_TYPE"] = "none"

api_key = os.getenv("OPENAI_API_KEY")
print("🔑 API Key is:", api_key)
client = OpenAI(api_key=api_key)
                
# Phase 1: Core MVP for Personal LLM Assistant with Local Memory (RAG + GPT-4)

# === 0. Imports ===
import faiss
import json
import streamlit as st
from typing import List
from PyPDF2 import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sentence_transformers import SentenceTransformer
import numpy as np

# === 1. Config ===
@st.cache_resource(show_spinner="Loading embedding model...")
def load_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer('all-MiniLM-L6-v2')

embed_model = load_model()

openai.api_key = os.getenv("OPENAI_API_KEY")
#embed_model = SentenceTransformer('all-MiniLM-L6-v2')  # Local embeddings
index = faiss.IndexFlatL2(384)  # Vector size for MiniLM
chunk_store = []  # To keep text chunks with metadata
uploaded_files_meta = []  # To track filenames and number of chunks

# === 2. Document Ingestion ===
def load_and_chunk_pdf(path, chunk_size=500):
    reader = PdfReader(path)
    raw_text = " ".join([page.extract_text() or '' for page in reader.pages])
    words = raw_text.split()
    return [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]

def embed_chunks(chunks: List[str]):
    embeddings = embed_model.encode(chunks)
    index.add(np.array(embeddings, dtype=np.float32))
    chunk_store.extend(chunks)

# === 3. Retrieval ===
def retrieve_relevant_chunks(query, k=5):
    if not chunk_store or index.ntotal == 0:
        return []  # No memory available yet
    query_vec = embed_model.encode([query]).astype('float32')
    D, I = index.search(query_vec, k)
    return [chunk_store[i] for i in I[0] if i < len(chunk_store)]

# === 4. Prompt Construction ===
def build_prompt(query, memory_chunks):
    context = "\n---\n".join(memory_chunks)
    return f"You are a helpful assistant. Use the following context to answer the question.\n\n{context}\n\nQuestion: {query}\nAnswer:"

# === 5. Query GPT-4 ===
def query_gpt(prompt):
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    answer = response.choices[0].message.content
    return answer or "⚠️ GPT-4 returned no answer."


# === 6. Streamlit UI ===
st.title("📚 Personal AI with Local Memory")

# Session State Initialization
if "uploaded_files_meta" not in st.session_state:
    st.session_state.uploaded_files_meta = []
uploaded_files_meta = st.session_state.uploaded_files_meta

# Memory Browser
with st.expander("🧠 View Uploaded Memory Chunks"):
    if not uploaded_files_meta:
        st.info("No memory chunks have been added yet.")
    else:
        to_delete = None  # Track which file to delete

        for i, file in enumerate(uploaded_files_meta):
            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(f"**📄 {file['filename']}** — {file['num_chunks']} chunks")
                for j, chunk in enumerate(file['chunks'][:3]):
                    st.markdown(f"- *Chunk {j+1}:* `{chunk[:150]}...`")
            with col2:
                if st.button("🗑️ Delete", key=f"delete_{i}"):
                    to_delete = i

        if to_delete is not None:
            # Remove chunks from FAISS and chunk_store
            removed = uploaded_files_meta[to_delete]
            start_idx = sum(f["num_chunks"] for f in uploaded_files_meta[:to_delete])
            index.remove_ids(faiss.IDSelectorRange(start_idx, start_idx + removed["num_chunks"]))
            del chunk_store[start_idx:start_idx + removed["num_chunks"]]
            del uploaded_files_meta[to_delete]
            st.experimental_rerun()
# Upload section
uploaded_file = st.file_uploader("Upload a document", type=["pdf", "txt"])
if uploaded_file is not None:
    file_ext = uploaded_file.name.split('.')[-1]

    if file_ext == "pdf":
        chunks = load_and_chunk_pdf(uploaded_file)
    elif file_ext == "txt":
        text = uploaded_file.read().decode("utf-8")
        words = text.split()
        chunks = [" ".join(words[i:i+500]) for i in range(0, len(words), 500)]
    else:
        chunks = []

    if chunks:
        embed_chunks(chunks)
        uploaded_files_meta.append({
            "id": len(uploaded_files_meta),
            "filename": uploaded_file.name,
            "num_chunks": len(chunks),
            "preview": chunks[:2],
            "chunks": chunks  # Store full chunks per file
        })
        st.success(f"Embedded {len(chunks)} chunks from {uploaded_file.name}")


# Question input
query = st.text_input("Ask something related to your uploaded document or past memory:")

if query:
    with st.spinner("Retrieving memory and querying GPT-4..."):
        memory = retrieve_relevant_chunks(query)

        if not memory:
            st.warning("⚠️ No memory found yet. Upload a PDF first!")
        else:
            prompt = build_prompt(query, memory)
            answer = query_gpt(prompt)

            st.markdown("### 🧠 Retrieved Memory Chunks:")
            for chunk in memory:
                st.markdown(f"- {chunk[:300]}...")

            st.markdown("### 🤖 GPT-4 Answer:")
            st.markdown(answer)