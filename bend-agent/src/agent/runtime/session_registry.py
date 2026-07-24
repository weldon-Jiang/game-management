"""SessionRegistry — 每个串流账号任务一个 MediaSession。"""

import threading
from typing import Dict, Optional

from ..core.logger import get_logger
from .session import StreamingSession


class SessionRegistry:
    _instance: Optional["SessionRegistry"] = None

    def __init__(self):
        self.logger = get_logger("session_registry")
        self._sessions: Dict[str, StreamingSession] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "SessionRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, task_id: str, session: StreamingSession) -> None:
        with self._lock:
            existing = self._sessions.get(task_id)
            if existing and existing is not session:
                self.logger.warning("Replacing session for task %s", task_id)
            self._sessions[task_id] = session

    def get_by_streaming_account(self, streaming_account_id: str) -> Optional[StreamingSession]:
        with self._lock:
            for session in self._sessions.values():
                creds = getattr(session, "credentials", None)
                if creds and creds.streaming_account_id == streaming_account_id:
                    return session
            return None

    def get(self, task_id: str) -> Optional[StreamingSession]:
        with self._lock:
            return self._sessions.get(task_id)

    def remove(self, task_id: str) -> None:
        with self._lock:
            self._sessions.pop(task_id, None)

    async def close_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            await session.close()
