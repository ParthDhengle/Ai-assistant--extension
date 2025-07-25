from .session_manager import SessionManager
from typing import List, Dict

class MemoryDB:
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the current session."""
        self.session_manager.add_message_to_session(role, content)

    def get_recent_messages(self, n: int = 5) -> List[Dict]:
        """Retrieve the last N messages from the current session."""
        return self.session_manager.get_last_n_messages(n)