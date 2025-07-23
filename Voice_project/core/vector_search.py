from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import os
import json


class VectorSearch:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.index = faiss.IndexFlatL2(384)  # Dimension of MiniLM embeddings
        self.texts = []
        self.index_file = "memory/faiss_index/index.faiss"
        self.texts_file = "memory/faiss_index/texts.json"
        self.load_index()

    def load_index(self):
        if not os.path.exists("memory/faiss_index"):
            os.makedirs("memory/faiss_index")
        if os.path.exists(self.index_file):
            self.index = faiss.read_index(self.index_file)
            with open(self.texts_file, 'r') as f:
                self.texts = json.load(f)

    def save_index(self):
        faiss.write_index(self.index, self.index_file)
        with open(self.texts_file, 'w') as f:
            json.dump(self.texts, f)

    def add_interaction(self, text):
        embedding = self.model.encode(text, convert_to_numpy=True)
        self.index.add(np.array([embedding]))
        self.texts.append(text)
        self.save_index()

    def search_similar(self, query, k=2):
        if not self.texts:
            return []
        query_embedding = self.model.encode(query, convert_to_numpy=True)
        distances, indices = self.index.search(np.array([query_embedding]), k)
        return [self.texts[i].split('\n')[-2:] for i in indices[0] if i < len(self.texts)]