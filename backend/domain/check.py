from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4


class CheckStatus(StrEnum):
    QUEUED = "queued"


@dataclass(frozen=True, slots=True)
class SubmittedDocument:
    filename: str
    content: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class Check:
    document: SubmittedDocument
    id: str = field(init=False, default_factory=lambda: f"chk_{uuid4().hex}")
    status: CheckStatus = field(init=False, default=CheckStatus.QUEUED)
