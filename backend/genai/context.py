"""Bounded, expiring context of SERVER retrievals; no client result upload."""
import secrets
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from backend.environment.schema import EnvironmentResponse


@dataclass(frozen=True)
class EnvironmentalContext:
    session_id: str
    environment: EnvironmentResponse
    source_mode: str
    created: float


class ContextStore:
    def __init__(self, ttl_seconds=900, max_entries=128, clock=time.monotonic):
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self.clock = clock
        self.entries = OrderedDict()
        self.lock = threading.Lock()

    def _expire(self):
        now = self.clock()
        for key in list(self.entries):
            if now - self.entries[key].created >= self.ttl:
                del self.entries[key]

    def save(self, session_id, environment, source_mode):
        if environment.status != 'ok' or not environment.results:
            return None
        with self.lock:
            self._expire()
            # Keep only the latest successful context per browser conversation.
            for key in list(self.entries):
                if self.entries[key].session_id == session_id:
                    del self.entries[key]
            token = secrets.token_urlsafe(32)
            self.entries[token] = EnvironmentalContext(session_id, environment.model_copy(deep=True), source_mode, self.clock())
            while len(self.entries) > self.max_entries:
                self.entries.popitem(last=False)
            return token

    def get(self, token, session_id):
        with self.lock:
            self._expire()
            entry = self.entries.get(token)
            if entry is None or not secrets.compare_digest(entry.session_id, session_id):
                return None
            return EnvironmentalContext(entry.session_id, entry.environment.model_copy(deep=True), entry.source_mode, entry.created)
