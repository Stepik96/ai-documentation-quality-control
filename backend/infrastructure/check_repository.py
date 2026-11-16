from threading import Lock

from backend.domain.check import Check


class InMemoryCheckRepository:
    def __init__(self):
        self._checks: dict[str, Check] = {}
        self._lock = Lock()

    def add(self, check: Check) -> None:
        with self._lock:
            if check.id in self._checks:
                raise ValueError(f"Check already exists: {check.id}")
            self._checks[check.id] = check
