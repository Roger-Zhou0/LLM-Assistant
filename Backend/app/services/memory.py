from typing import List
from sentence_transformers import SentenceTransformer, util
import numpy as np
import torch

_MODEL = SentenceTransformer("all-MiniLM-L6-v2")


class MemoryStore:
    def __init__(self):
        self.model = _MODEL
        self.texts = []
        self.embeddings = []

    def add(self, texts: List[str]):
        embeddings = self.model.encode(texts, convert_to_tensor=True)
        self.texts.extend(texts)
        self.embeddings.extend([emb for emb in embeddings]) 

    def query(self, text: str, top_k: int = 5) -> List[str]:
        if not self.embeddings:
            return []

        embedding_tensor = torch.stack(self.embeddings) if self.embeddings else torch.empty(0)


        query_embedding = self.model.encode(text, convert_to_tensor=True)
        similarities = util.pytorch_cos_sim(query_embedding, embedding_tensor)[0]
        top_indices = np.argsort(-similarities.cpu().numpy())[:top_k]

        return [self.texts[i] for i in top_indices]
    
