from io import BytesIO
from unittest import TestCase

from werkzeug.datastructures import MultiDict

from backend.core.submit_check import SubmitCheck
from backend.domain.check import Check, CheckStatus
from backend.http import MAX_REQUEST_BYTES, create_app
from backend.infrastructure.docx import DocxInspector
from backend.tests.fixtures import MANIFEST, sample_docx

CHECKS_URL = "/api/v1/checks"


class RecordingCheckRepository:
    def __init__(self):
        self.checks: list[Check] = []

    def add(self, check: Check) -> None:
        self.checks.append(check)


class DocumentIntakeTest(TestCase):
    def setUp(self):
        self.repository = RecordingCheckRepository()
        app = create_app(SubmitCheck(DocxInspector(), self.repository))
        app.testing = True
        self.client = app.test_client()

    def upload(self, content: bytes, filename: str):
        return self.client.post(CHECKS_URL, data={"file": (BytesIO(content), filename)})

    def assert_rejection(self, response, status, code):
        self.assertEqual(response.status_code, status)
        error = response.json["error"]
        self.assertEqual(error["code"], code)
        self.assertTrue(error["message"].strip())
        self.assertEqual(self.repository.checks, [])

    def test_accepts_and_saves_each_submission_with_its_own_id(self):
        content = sample_docx()
        for _ in range(2):
            response = self.upload(content, "Тест.DOCX")
            self.assertEqual(response.status_code, 202)
            saved = self.repository.checks[-1]
            self.assertEqual(response.json, {"checkId": saved.id, "status": "queued"})
            self.assertEqual(saved.status, CheckStatus.QUEUED)
            self.assertEqual(saved.document.filename, "Тест.DOCX")
            self.assertEqual(saved.document.content, content)

        first, second = self.repository.checks
        self.assertNotEqual(first.id, second.id)

    def test_rejects_missing_or_non_file_value(self):
        for data in ({}, {"file": "text"}, {"other": (BytesIO(b"text"), "other.txt")},
                     {"file": (BytesIO(), "")}):
            with self.subTest(data=data):
                response = self.client.post(CHECKS_URL, data=data, content_type="multipart/form-data")
                self.assert_rejection(response, 400, "FILE_REQUIRED")

    def test_rejects_multiple_files(self):
        for second_field in ("file", "other"):
            with self.subTest(second_field=second_field):
                data = MultiDict([
                    ("file", (BytesIO(sample_docx()), "first.docx")),
                    (second_field, (BytesIO(sample_docx()), "second.docx")),
                ])
                response = self.client.post(CHECKS_URL, data=data)
                self.assert_rejection(response, 400, "INVALID_REQUEST")

    def test_rejects_unsupported_extension(self):
        response = self.upload(b"text", "example.txt")
        self.assert_rejection(response, 415, "UNSUPPORTED_FILE_FORMAT")

    def test_rejects_invalid_docx(self):
        invalid_documents = {
            "empty": b"",
            "renamed text": b"text",
            "wrong content type": sample_docx(MANIFEST.replace("document.main+xml", "template.main+xml")),
            "invalid manifest": sample_docx("<Types>"),
            "unsupported encoding": sample_docx('<?xml version="1.0" encoding="unknown"?><Types/>'),
        }
        for case, content in invalid_documents.items():
            with self.subTest(case=case):
                response = self.upload(content, "example.docx")
                self.assert_rejection(response, 422, "INVALID_DOCUMENT")

    def test_rejects_oversized_request(self):
        response = self.upload(b"x" * MAX_REQUEST_BYTES, "oversized.docx")
        self.assert_rejection(response, 413, "FILE_TOO_LARGE")
