import json
import os
from core.vector_search import VectorSearch
from utils.text_utils import estimate_tokens
import requests

class MemoryManager:
    def __init__(self):
        self.memory_file = "memory/memory.json"
        self.summary_file = "memory/summary.json"
        self.vector_search = VectorSearch()
        self.max_recent = 3
        self.summary_interval = 10
        self.max_tokens = 5000
        self.load_memory()

    def load_memory(self):
        if not os.path.exists("memory"):
            os.makedirs("memory")
        if not os.path.exists(self.memory_file):
            with open(self.memory_file, 'w') as f:
                json.dump([], f)
        if not os.path.exists(self.summary_file):
            with open(self.summary_file, 'w') as f:
                json.dump("", f)

    def get_recent_memory(self, n):
        if not os.path.exists(self.memory_file):
            return []
        try:
            with open(self.memory_file, 'r') as f:
                content = f.read()
                
                if not content:  # Handle empty file
                    return []
                memory = json.loads(content)
            return memory[-n:] if len(memory) >= n else memory
        except json.JSONDecodeError as e:
            print(f"Error loading memory: Invalid JSON - {e}")
            return []
        except Exception as e:
            print(f"Error loading memory: {e}")
            return []
    def get_summary(self):
        if not os.path.exists(self.summary_file):
            print(f"Summary file does not exist: {self.summary_file}")
            return ""
        try:
            with open(self.summary_file, 'r') as f:
                content = f.read()
                print(f"Summary file content: {content}")
                if not content:  # Handle empty file
                    print("Summary file is empty")
                    return ""
                summary = json.loads(content)
            return summary
        except json.JSONDecodeError as e:
            print(f"Error loading summary: Invalid JSON - {e}")
            return ""
        except Exception as e:
            print(f"Error loading summary: {e}")
            return ""

    def update_summary(self):
        with open(self.memory_file, 'r') as f:
            memory = json.load(f)
        if len(memory) < self.summary_interval:
            return
        summary_prompt = (
            "Summarize the following conversation history into a concise paragraph:\n" +
            "\n".join([f"You: {u}\nSpark: {b}" for u, b in memory])
        )
        try:
            response = requests.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": "phi3:3.8b",
                    "messages": [
                        {"role": "system", "content": "You are a summarizer."},
                        {"role": "user", "content": summary_prompt}
                    ],
                    "stream": False
                },
                timeout=30
            )
            response.raise_for_status()
            summary = response.json().get('message', {}).get('content', '')
            with open(self.summary_file, 'w') as f:
                json.dump(summary, f)
        except Exception as e:
            print(f"❌ Summary update failed: {e}")

    def add_to_memory(self, user, bot):
        try:
            with open(self.memory_file, 'r') as f:
                content = f.read().strip()
                if content:
                    memory = json.loads(content)
                else:
                    memory = []
        except (FileNotFoundError, json.JSONDecodeError):
            memory = []
        memory.append((user, bot))

        with open(self.memory_file, 'w') as f:
            json.dump(memory, f)
            print(f"Memory updated: {len(memory)} entries")
        self.vector_search.add_interaction(f"You: {user}\nSpark: {bot}")
        if len(memory) % self.summary_interval == 0:
            self.update_summary()

    def get_relevant_memory(self, query, k=2):
        return self.vector_search.search_similar(query, k)

    def get_context(self, query):
        recent = self.get_recent_memory(self.max_recent)
        summary = self.get_summary()
        vector_hits = self.get_relevant_memory(query, k=2)
        context = {
            "summary": summary,
            "recent": recent,
            "vector_hits": vector_hits
        }
        total_tokens = estimate_tokens(
            f"{summary}\n" + "\n".join([f"You: {u}\nSpark: {b}" for u, b in recent]) +
            "\n" + "\n".join([f"You: {u}\nSpark: {b}" for u, b in vector_hits]) +
            f"\n{query}"
        )
        while total_tokens > self.max_tokens * 0.8:  # Keep under 80% of limit
            if vector_hits:
                vector_hits.pop()
            elif len(recent) > 1:
                recent.pop(0)
            total_tokens = estimate_tokens(
                f"{summary}\n" + "\n".join([f"You: {u}\nSpark: {b}" for u, b in recent]) +
                "\n" + "\n".join([f"You: {u}\nSpark: {b}" for u, b in vector_hits]) +
                f"\n{query}"
            )
        return context