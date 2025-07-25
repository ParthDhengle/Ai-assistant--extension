from .session_manager import SessionManager
from .memory_db import MemoryDB
from .vector_db import VectorDB
from .summarizer import Summarizer
from .user_profile import UserProfileManager
from typing import Dict, List, Any

class MemoryManager:
    def __init__(self):
        self.session_manager = SessionManager()
        self.memory_db = MemoryDB(self.session_manager)
        self.vector_db = VectorDB()
        self.summarizer = Summarizer()
        self.user_profile_manager = UserProfileManager()
        self.current_session_id = self.session_manager.start_new_session()

    def add_message(self, role: str, content: str) -> None:
        """Add a message to memory and vector DB."""
        message = self.memory_db.add_message(role, content)
        if message:
            self.vector_db.add_message(content, {
                "session_id": self.current_session_id,
                "message_id": len(self.session_manager.current_session["messages"]) - 1,
                "timestamp": message["timestamp"],
                "topics": []  # Can be extended with topic extraction
            })

    def get_context_for_llm(self, query: str) -> Dict[str, Any]:
        """Prepare context for LLM query."""
        recent_messages = self.memory_db.get_recent_messages(5)
        similar_messages = self.vector_db.search_similar(query, k=2)
        relevant_past = [msg["text"] for msg in similar_messages]
        user_profile = self.user_profile_manager.get_profile()

        all_messages = recent_messages
        if self.summarizer.check_token_limit(all_messages):
            all_messages = self.summarizer.summarize_old_messages(all_messages)

        context = {
            "user_profile": user_profile,
            "summary": all_messages[0]["content"] if all_messages and all_messages[0]["role"] == "system" else "",
            "recent_messages": all_messages if not all_messages or all_messages[0]["role"] != "system" else all_messages[1:],
            "relevant_past": relevant_past
        }
        return context

    def update_user_profile(self, key: str, value: Any) -> None:
        """Update user profile with confirmed facts."""
        self.user_profile_manager.update_profile(key, value)