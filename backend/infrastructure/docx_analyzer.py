from io import BytesIO
from zipfile import ZipFile

from docx import Document
from docx.table import Table

from backend.domain.check import CheckResult, DocumentProfile, SubmittedDocument
from backend.domain.heading_rule import MISSING_HEADING, is_level_one_heading
from backend.infrastructure.docx_style_checks import check_object_bold, check_table_font, check_table_references

MAX_UNPACKED_BYTES = 64 * 1024 * 1024


class DocxAnalyzer:
    def analyze(self, document: SubmittedDocument) -> CheckResult:
        source = BytesIO(document.content)
        with ZipFile(source) as package:
            if sum(part.file_size for part in package.infolist()) > MAX_UNPACKED_BYTES:
                raise ValueError("DOCX exceeds the unpacked size limit")
        source.seek(0)
        docx = Document(source)
        if document.profile == DocumentProfile.TECH_SPEC:
            blocks = list(docx.iter_inner_content())
            tables = [block for block in blocks if isinstance(block, Table)]
            size_findings, size_unchecked = check_table_font(docx, tables)
            reference_findings, reference_unchecked = check_table_references(blocks)
            return CheckResult(
                "candidate-r02-r03-v1",
                tuple(size_findings + reference_findings),
                tuple(size_unchecked + reference_unchecked),
            )
        if document.profile == DocumentProfile.USER_GUIDE:
            return CheckResult("candidate-r01-v1", tuple(check_object_bold(docx)))
        has_heading = any(
            is_level_one_heading(paragraph.text, paragraph.style.name, paragraph.style.builtin)
            for paragraph in docx.paragraphs
        )
        findings = () if has_heading else (MISSING_HEADING,)
        return CheckResult("heading-1", findings)
