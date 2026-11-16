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

    def get(self, check_id: str) -> Check | None:
        with self._lock:
            return self._checks.get(check_id)

    def update(self, check: Check) -> None:
        with self._lock:
            if check.id not in self._checks:
                raise KeyError(check.id)
            self._checks[check.id] = check
