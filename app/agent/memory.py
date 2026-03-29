"""Persistent rolling conversation history."""
from __future__ import annotations
import json
from pathlib import Path

_DEFAULT_PATH = Path.home() / ".agentbk" / "history.json"
_MAX_MESSAGES = 100


class ConversationMemory:
    def __init__(self, path: Path = _DEFAULT_PATH) -> None:
        self._path = path
        self._messages: list[dict] = []
        self._load()

    @property
    def messages(self) -> list[dict]:
        return self._messages

    def add(self, role: str, content: str) -> None:
        self._messages.append({"role": role, "content": content})
        self._trim()

    def persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(self._messages, f, ensure_ascii=False, indent=2)
        tmp.replace(self._path)

    def clear(self) -> None:
        self._messages = []
        if self._path.exists():
            self._path.unlink()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                self._messages = data
                self._trim()
        except (json.JSONDecodeError, OSError):
            self._messages = []

    def _trim(self) -> None:
        if len(self._messages) > _MAX_MESSAGES:
            self._messages = self._messages[-_MAX_MESSAGES:]
