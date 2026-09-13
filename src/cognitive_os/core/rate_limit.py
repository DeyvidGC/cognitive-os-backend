from collections import deque
from threading import Lock
from time import monotonic


class AuthRateLimiter:
    """Bounded per-process limiter. Use a shared gateway limiter for multiple workers."""

    def __init__(self, limit: int = 20, window: int = 60):
        self.limit = limit
        self.window = window
        self.clients: dict[str, deque[float]] = {}
        self.lock = Lock()

    def allow(self, client: str) -> bool:
        now = monotonic()
        with self.lock:
            expired = [key for key, values in self.clients.items() if values[-1] <= now - self.window]
            for key in expired:
                del self.clients[key]
            if client not in self.clients and len(self.clients) >= 4096:
                return False
            values = self.clients.setdefault(client, deque())
            while values and values[0] <= now - self.window:
                values.popleft()
            if len(values) >= self.limit:
                return False
            values.append(now)
            return True
