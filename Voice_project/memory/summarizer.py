import requests
from typing import List, Dict
from .utils.token_counter import estimate_tokens

class Summarizer:
    def __init__(self, max_tokens: int = 8000):
        self.max_tokens = max_tokens

    def check_token_limit(self, messages: List[Dict]) -> bool:
        """Check if total token count exceeds the limit."""
        total_tokens = sum(estimate_tokens(msg["content"]) for msg in messages)
        return total_tokens > self.max_tokens

    def summarize_old_messages(self, messages: List[Dict]) -> List[Dict]:
        """Summarize older messages, keeping last 5 intact."""
        if len(messages) <= 5:
            return messages
        recent_messages = messages[-5:]
        older_messages = messages[:-5]

        summary_prompt = (
            "Summarize the following conversation history into a concise paragraph:\n" +
            "\n".join([f"{msg['role']}: {msg['content']}" for msg in older_messages])
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
            return [{"role": "system", "content": f"Summary of previous messages: {summary}", "timestamp": messages[0]["timestamp"]}] + recent_messages
        except Exception as e:
            print(f"❌ Summary update failed: {e}")
            return messages  # Fallback to original messages