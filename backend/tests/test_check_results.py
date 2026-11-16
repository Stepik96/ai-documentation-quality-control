from io import BytesIO
from pathlib import Path
from time import monotonic, sleep
from unittest import TestCase
from zipfile import ZipFile

from backend.http import create_app
from backend.tests.fixtures import sample_docx
from backend.tests.rule_fixtures import tech_spec, user_guide

FIXTURES = Path(__file__).resolve().parents[2] / "scripts" / "fixtures"
CHECKS_URL = "/api/v1/checks"


class CheckResultsTest(TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def check_document(self, filename, content, profile=None):
        fields = {"file": (BytesIO(content), filename)}
        if profile is not None:
            fields["profile"] = profile
        accepted = self.client.post(CHECKS_URL, data=fields)
        self.assertEqual(accepted.status_code, 202)
        self.assertEqual(accepted.json["status"], "queued")
        url = f"{CHECKS_URL}/{accepted.json['checkId']}"
        deadline = monotonic() + 3
        while monotonic() < deadline:
            status = self.client.get(url)
            self.assertEqual(status.status_code, 200)
            if status.json["status"] in {"completed", "failed"}:
                return status.json, self.client.get(f"{url}/result")
            sleep(0.01)
        self.fail(f"Check did not finish: {url}")

    def test_reports_actual_heading_style(self):
        for filename, count in (("with-heading.docx", 0), ("with-bold-text.docx", 1)):
            with self.subTest(filename=filename):
                status, result = self.check_document(filename, (FIXTURES / filename).read_bytes())
                self.assertEqual(status["status"], "completed")
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json["checkId"], status["checkId"])
                self.assertEqual(result.json["summary"]["findingCount"], count)
                self.assertEqual(len(result.json["findings"]), count)
                if count:
                    self.assertEqual(result.json["findings"][0]["ruleId"], "DOCX-HEADING-01")

    def test_reports_processing_failure_for_malformed_document_xml(self):
        output = BytesIO()
        with ZipFile(BytesIO(sample_docx())) as original, ZipFile(output, "w") as damaged:
            for name in original.namelist():
                damaged.writestr(name, b"<broken" if name == "word/document.xml" else original.read(name))
        status, result = self.check_document("damaged.docx", output.getvalue())
        self.assertEqual(status["status"], "failed")
        self.assertEqual(status["error"]["code"], "CHECK_FAILED")
        self.assertEqual(result.status_code, 409)
        self.assertEqual(result.json["error"]["code"], "CHECK_FAILED")

    def test_unknown_check_returns_structured_not_found(self):
        for suffix in ("", "/result"):
            response = self.client.get(f"{CHECKS_URL}/unknown{suffix}")
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json["error"]["code"], "CHECK_NOT_FOUND")

    def test_technical_spec_checks_size_and_references_independently(self):
        for size, referenced, expected in (
            (10, True, []),
            (12, True, ["R02"]),
            (10, False, ["R03"]),
            (12, False, ["R02", "R03"]),
        ):
            with self.subTest(size=size, referenced=referenced):
                status, result = self.check_document(
                    "technical.docx", tech_spec(size=size, referenced=referenced), "tech-spec",
                )
                self.assertEqual(status["status"], "completed")
                self.assertEqual(result.json["profile"], "tech-spec")
                self.assertEqual(result.json["completeness"], "complete")
                self.assertEqual([item["ruleId"] for item in result.json["findings"]], expected)

    def test_user_guide_requires_bold_across_runs(self):
        for fully_bold, expected in ((True, []), (False, ["R01"])):
            with self.subTest(fully_bold=fully_bold):
                status, result = self.check_document(
                    "guide.docx", user_guide(fully_bold=fully_bold), "user-guide",
                )
                self.assertEqual(status["status"], "completed")
                self.assertEqual([item["ruleId"] for item in result.json["findings"]], expected)

    def test_rejects_unknown_profile(self):
        response = self.client.post(CHECKS_URL, data={
            "file": (BytesIO(sample_docx()), "sample.docx"),
            "profile": "unknown",
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["error"]["code"], "INVALID_PROFILE")
