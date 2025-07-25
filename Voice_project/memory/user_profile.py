import json
import os
from typing import Dict, Any

class UserProfileManager:
    def __init__(self, profile_path: str = "memory/user_profile.json"):
        self.profile_path = profile_path
        self.profile = self._load_profile()

    def _load_profile(self) -> Dict[str, Any]:
        """Load the user profile from disk, create if not exists."""
        try:
            if os.path.exists(self.profile_path):
                with open(self.profile_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ Error loading profile: {e}, starting with empty profile")
            return {}

    def _save_profile(self) -> None:
        """Save the user profile to disk with error handling."""
        try:
            os.makedirs(os.path.dirname(self.profile_path), exist_ok=True)
            with open(self.profile_path, 'w', encoding='utf-8') as f:
                json.dump(self.profile, f, indent=2)
        except IOError as e:
            print(f"❌ Error saving profile: {e}")

    def update_profile(self, key: str, value: Any) -> None:
        """Update a key-value pair in the profile and save."""
        self.profile[key] = value
        self._save_profile()

    def get_profile(self) -> Dict[str, Any]:
        """Get the current user profile."""
        return self.profile