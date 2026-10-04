"""Persist desktop preferences without changing camera state."""
import json
import os
from pathlib import Path


class UpdatePreferences:
    def __init__(self, path):
        self.path = Path(path)
        try:
            value = json.loads(self.path.read_text(encoding='utf-8')).get('autoCheckUpdates')
        except (OSError, ValueError, AttributeError):
            value = None
        self.auto_check = value if isinstance(value, bool) else True

    def set_auto_check(self, enabled):
        self.auto_check = bool(enabled)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps({'autoCheckUpdates': self.auto_check})+'\n', encoding='utf-8')
            os.replace(temporary, self.path)
        except OSError:
            return False
        return True
