"""
Conversation Manager for multi-turn follow-up support.

Manages conversation sessions with history, allowing Grok API to receive
multi-turn context for follow-up questions.
"""

import asyncio
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Message:
    """A single message in a conversation."""
    role: str       # "user" | "assistant" | "system"
    content: str


@dataclass
class ConversationSession:
    """A conversation session with message history."""
    session_id: str
    messages: list[Message] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_access: float = field(default_factory=time.time)
    search_count: int = 0

    def add_user_message(self, content: str) -> None:
        self.messages.append(Message(role="user", content=content))
        self.last_access = time.time()
        self.search_count += 1

    def add_assistant_message(self, content: str) -> None:
        self.messages.append(Message(role="assistant", content=content))
        self.last_access = time.time()

    def get_history(self) -> list[dict]:
        """Return messages as list of dicts for API consumption."""
        return [{"role": m.role, "content": m.content} for m in self.messages]

    def is_expired(self, timeout_seconds: int) -> bool:
        return (time.time() - self.last_access) > timeout_seconds

    def is_over_limit(self, max_searches: int) -> bool:
        return self.search_count >= max_searches


# Configurable via environment variables
SESSION_TIMEOUT = int(os.getenv("GROK_SESSION_TIMEOUT", "600"))       # 10 min
MAX_SESSIONS = int(os.getenv("GROK_MAX_SESSIONS", "20"))              # max concurrent sessions
MAX_SEARCHES_PER_SESSION = int(os.getenv("GROK_MAX_SEARCHES", "50"))  # max turns per session


class ConversationManager:
    """Manages multiple conversation sessions for follow-up support."""

    def __init__(
        self,
        max_sessions: int = MAX_SESSIONS,
        session_timeout: int = SESSION_TIMEOUT,
        max_searches: int = MAX_SEARCHES_PER_SESSION,
    ):
        self._sessions: dict[str, ConversationSession] = {}
        self._lock = asyncio.Lock()
        self._max_sessions = max_sessions
        self._session_timeout = session_timeout
        self._max_searches = max_searches

    def new_session_id(self) -> str:
        return uuid.uuid4().hex[:12]

    async def get_or_create(self, session_id: str = "") -> ConversationSession:
        """Get existing session or create a new one."""
        async with self._lock:
            # Cleanup expired sessions first
            self._cleanup_expired()

            # Return existing session if valid
            if session_id and session_id in self._sessions:
                session = self._sessions[session_id]
                if not session.is_expired(self._session_timeout) and not session.is_over_limit(self._max_searches):
                    return session
                else:
                    # Session expired or over limit, remove it
                    del self._sessions[session_id]

            # Evict oldest session if at capacity
            if len(self._sessions) >= self._max_sessions:
                oldest_id = min(self._sessions, key=lambda k: self._sessions[k].last_access)
                del self._sessions[oldest_id]

            # Create new session
            new_id = session_id if session_id else self.new_session_id()
            session = ConversationSession(session_id=new_id)
            self._sessions[new_id] = session
            return session

    async def get(self, session_id: str) -> Optional[ConversationSession]:
        """Get an existing session, or None if not found/expired."""
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if session.is_expired(self._session_timeout) or session.is_over_limit(self._max_searches):
                del self._sessions[session_id]
                return None
            return session

    async def remove(self, session_id: str) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)

    def _cleanup_expired(self) -> None:
        """Remove all expired or over-limit sessions. Call under lock."""
        expired = [
            sid for sid, s in self._sessions.items()
            if s.is_expired(self._session_timeout) or s.is_over_limit(self._max_searches)
        ]
        for sid in expired:
            del self._sessions[sid]

    async def stats(self) -> dict:
        async with self._lock:
            self._cleanup_expired()
            return {
                "active_sessions": len(self._sessions),
                "max_sessions": self._max_sessions,
                "session_timeout_seconds": self._session_timeout,
                "sessions": [
                    {
                        "session_id": s.session_id,
                        "search_count": s.search_count,
                        "age_seconds": int(time.time() - s.created_at),
                        "idle_seconds": int(time.time() - s.last_access),
                    }
                    for s in self._sessions.values()
                ],
            }


# Global singleton
conversation_manager = ConversationManager()
