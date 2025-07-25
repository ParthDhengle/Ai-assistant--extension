import json
import os
import uuid
from datetime import datetime
from typing import List, Dict, Optional

class SessionManager:
    def __init__(self, sessions_dir: str = "memory/sessions"):
        self.sessions_dir = sessions_dir
        os.makedirs(sessions_dir, exist_ok=True)
        self.current_session: Optional[Dict] = None

    def start_new_session(self) -> str:
        """Start a new session with a unique ID."""
        session_id = f"session_{uuid.uuid4().hex}"
        self.current_session = {
            "session_id": session_id,
            "start_time": datetime.now().isoformat(),
            "messages": []
        }
        self._save_session()
        return session_id

    def load_session(self, session_id: str) -> bool:
        """Load an existing session by ID."""
        session_file = os.path.join(self.sessions_dir, f"{session_id}.json")
        try:
            if os.path.exists(session_file):
                with open(session_file, 'r', encoding='utf-8') as f:
                    self.current_session = json.load(f)
                return True
            return False
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ Error loading session {session_id}: {e}")
            return False

    def _save_session(self) -> None:
        """Save the current session to disk."""
        if not self.current_session:
            return
        session_file = os.path.join(self.sessions_dir, f"{self.current_session['session_id']}.json")
        try:
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_session, f, indent=2)
        except IOError as e:
            print(f"❌ Error saving session: {e}")

    def add_message_to_session(self, role: str, content: str) -> Optional[Dict]:
        """Add a message to the current session."""
        if not self.current_session:
            return None
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        self.current_session["messages"].append(message)
        self._save_session()
        return message

    def get_last_n_messages(self, n: int = 5) -> List[Dict]:
        """Get the last N messages from the current session."""
        if not self.current_session:
            return []
        return self.current_session["messages"][-n:]