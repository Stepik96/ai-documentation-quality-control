from typing import Protocol

from backend.domain.check import Check, SubmittedDocument


class DocumentInspector(Protocol):
    def is_valid(self, content: bytes) -> bool: ...


class CheckRepository(Protocol):
    def add(self, check: Check) -> None: ...


class UnsupportedFileFormat(ValueError):
    pass


class InvalidDocument(ValueError):
    pass


class SubmitCheck:
    def __init__(self, inspector: DocumentInspector, repository: CheckRepository):
        self._inspector = inspector
        self._repository = repository

    def execute(self, document: SubmittedDocument) -> Check:
        if not document.filename.lower().endswith(".docx"):
            raise UnsupportedFileFormat
        if not self._inspector.is_valid(document.content):
            raise InvalidDocument

        check = Check(document)
        self._repository.add(check)
        return check
