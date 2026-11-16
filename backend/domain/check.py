from dataclasses import dataclass, field, replace
from enum import StrEnum
from uuid import uuid4


class CheckStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Finding:
    location: str
    rule_id: str
    rule: str
    problem: str
    recommendation: str
    category: str = "Структура и ссылки"


@dataclass(frozen=True, slots=True)
class CheckResult:
    rules_version: str
    findings: tuple[Finding, ...]
    unchecked: tuple[str, ...] = ()


class DocumentProfile(StrEnum):
    HEADING_DEMO = "heading-demo"
    TECH_SPEC = "tech-spec"
    USER_GUIDE = "user-guide"


@dataclass(frozen=True, slots=True)
class SubmittedDocument:
    filename: str
    content: bytes = field(repr=False)
    profile: DocumentProfile = DocumentProfile.HEADING_DEMO


@dataclass(frozen=True, slots=True)
class Check:
    document: SubmittedDocument
    id: str = field(default_factory=lambda: f"chk_{uuid4().hex}")
    status: CheckStatus = CheckStatus.QUEUED
    result: CheckResult | None = None

    def start(self) -> "Check":
        if self.status != CheckStatus.QUEUED:
            raise ValueError("Only a queued check can start")
        return replace(self, status=CheckStatus.PROCESSING)

    def finish(self, result: CheckResult | None) -> "Check":
        if self.status != CheckStatus.PROCESSING:
            raise ValueError("Only a processing check can finish")
        status = CheckStatus.COMPLETED if result is not None else CheckStatus.FAILED
        return replace(self, status=status, result=result)
