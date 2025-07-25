from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import json
import os
from typing import List, Dict

class VectorDB:
    def __init__(self, index_file: str = "memory/faiss_index/index.faiss", texts_file: str = "memory/faiss_index/texts.json"):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.index = faiss.IndexFlatL2(384)  # MiniLM embedding dimension
        self.texts: List[Dict] = []
        self.index_file = index_file
        self.texts_file = texts_file
        self._load_index()

    def _load_index(self) -> None:
        """Load existing FAISS index and texts."""
        os.makedirs(os.path.dirname(self.index_file), exist_ok=True)
        try:
            if os.path.exists(self.index_file):
                self.index = faiss.read_index(self.index_file)
                with open(self.texts_file, 'r', encoding='utf-8') as f:
                    self.texts = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"⚠️ Error loading vector DB: {e}, starting fresh")

    def _save_index(self) -> None:
        """Save FAISS index and texts to disk."""
        try:
            faiss.write_index(self.index, self.index_file)
            with open(self.texts_file, 'w', encoding='utf-8') as f:
                json.dump(self.texts, f)
        except IOError as e:
            print(f"❌ Error saving vector DB: {e}")

    def add_message(self, text: str, metadata: Dict) -> None:
        """Add a message embedding to the vector DB."""
        embedding = self.model.encode(text, convert_to_numpy=True)
        self.index.add(np.array([embedding]))
        self.texts.append({"text": text, "metadata": metadata})
        self._save_index()

    def search_similar(self, query: str, k: int = 2) -> List[Dict]:
        """Search for similar messages based on query."""
        if not self.texts:
            return []
        query_embedding = self.model.encode(query, convert_to_numpy=True)
        distances, indices = self.index.search(np.array([query_embedding]), k)
        return [self.texts[i] for i in indices[0] if i < len(self.texts)]