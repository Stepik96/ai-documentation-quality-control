from logging import getLogger
from typing import Protocol

from backend.domain.check import Check, CheckResult, SubmittedDocument

logger = getLogger(__name__)


class CheckStore(Protocol):
    def get(self, check_id: str) -> Check | None: ...
    def update(self, check: Check) -> None: ...


class DocumentAnalyzer(Protocol):
    def analyze(self, document: SubmittedDocument) -> CheckResult: ...


class ProcessCheck:
    def __init__(self, store: CheckStore, analyzer: DocumentAnalyzer):
        self._store = store
        self._analyzer = analyzer

    def execute(self, check: Check) -> None:
        processing = check.start()
        self._store.update(processing)
        try:
            result = self._analyzer.analyze(processing.document)
        except Exception:
            logger.warning("Could not analyze check %s", check.id)
            result = None
        self._store.update(processing.finish(result))
