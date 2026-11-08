"""Where conversation state lives between requests."""

import time
from collections import OrderedDict
from typing import Protocol

from backend.core.config import ContextConfig
from backend.nlp.context.resolver import ContextResolver
from backend.nlp.context.state import ConversationState, ResolvedTurn, TurnParse


class SessionStore(Protocol):
    """Anything with these two methods can hold the state: this in-memory
    store now, Redis or the database later, without touching the pipeline."""

    def get(self, session_id: str, now: float) -> ConversationState | None: ...

    def save(self, session_id: str, state: ConversationState) -> None: ...


class InMemorySessionStore:
    """State in a dictionary. Lost on restart, and not shared between
    processes: fine for one development server, not for deployment."""

    def __init__(self, config: ContextConfig) -> None:
        self._config = config
        self._sessions: OrderedDict[str, ConversationState] = OrderedDict()

    def get(self, session_id: str, now: float) -> ConversationState | None:
        state = self._sessions.get(session_id)
        if state is None:
            return None
        if now - state.updated_at > self._config.max_idle_seconds:
            del self._sessions[session_id]
            return None
        return state

    def save(self, session_id: str, state: ConversationState) -> None:
        self._sessions[session_id] = state
        self._sessions.move_to_end(session_id)
        while len(self._sessions) > self._config.max_sessions:
            self._sessions.popitem(last=False)  # drop the least recently used

    def __len__(self) -> int:
        return len(self._sessions)


class ConversationManager:
    """Load state, resolve the turn against it, store the result."""

    def __init__(self, config: ContextConfig, store: SessionStore | None = None) -> None:
        self._resolver = ContextResolver(config)
        # `store or ...` would be wrong: an empty store has length 0 and is falsy.
        self._store = store if store is not None else InMemorySessionStore(config)

    def language_of(self, session_id: str | None, now: float | None = None):
        """Language of the previous turn, used as the language-detection fallback."""
        if session_id is None:
            return None
        state = self._store.get(session_id, time.time() if now is None else now)
        return state.language if state else None

    def process(self, session_id: str | None, turn: TurnParse,
                now: float | None = None) -> ResolvedTurn:
        """Without a session id, the turn is handled with no memory at all."""
        if session_id is None:
            return self._resolver.resolve(turn, None)
        now = time.time() if now is None else now
        state = self._store.get(session_id, now)
        resolved = self._resolver.resolve(turn, state)
        self._store.save(session_id, self._resolver.update(state, turn, resolved, now))
        return resolved
