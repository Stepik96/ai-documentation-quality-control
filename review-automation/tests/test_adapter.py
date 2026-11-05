import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from test_controller import fixture
import controller as c


class CodexAdapter(unittest.TestCase):
    def test_stdin_schema_and_no_github_credentials(self):
        policy, snapshot, result = fixture()
        observed = {}
        def fake_run(command, **kwargs):
            if command[1:] == ["login", "status"]:
                return subprocess.CompletedProcess(command, 0, 'Logged in using ChatGPT', '')
            observed.update(kwargs)
            self.assertIn("--ignore-user-config", command)
            self.assertIn("shell_tool", command)
            self.assertIn("--output-schema", command)
            self.assertNotIn("REVIEW_GITHUB_TOKEN", kwargs["env"])
            self.assertNotIn("OPENAI_API_KEY", kwargs["env"])
            self.assertIn("You are PR-Reviewer", kwargs["input"])
            self.assertIn("UNTRUSTED_DATA_JSON", kwargs["input"])
            Path(command[command.index("-o") + 1]).write_text(json.dumps(result), encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, '{"type":"turn.completed"}\n', '')
        with patch.dict(os.environ, {"REVIEW_GITHUB_TOKEN": "fake-only", "OPENAI_API_KEY": "fake-only"}), patch("controller.shutil.which", return_value="codex.cmd"), patch("controller.run_process", side_effect=fake_run):
            self.assertEqual(c.codex_analyze(snapshot, None, policy), result)
        self.assertEqual(observed["timeout"], 600)

    def test_cli_nonzero_fails_closed_without_logging_output(self):
        policy, snapshot, _ = fixture()
        with patch("controller.shutil.which", return_value="codex.cmd"), patch("controller.run_process", return_value=subprocess.CompletedProcess([], 1, '', 'private-error-details')):
            with self.assertRaises(c.Stop) as error:
                c.codex_analyze(snapshot, None, policy)
        self.assertNotIn("private-error-details", str(error.exception))

    def test_timeout_fails_closed(self):
        policy, snapshot, _ = fixture()
        with patch("controller.shutil.which", return_value="codex.cmd"), patch("controller.run_process", side_effect=subprocess.TimeoutExpired([], 600)):
            with self.assertRaises(c.Stop):
                c.codex_analyze(snapshot, None, policy)

    def test_actual_process_timeout(self):
        import sys
        with self.assertRaises(subprocess.TimeoutExpired):
            c.run_process([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.1)

    def test_github_uses_official_credential_manager_without_exposing_secret(self):
        with patch.dict(os.environ, {}, clear=True), patch("controller.run_process", return_value=subprocess.CompletedProcess([], 0, "username=Stepik96\npassword=fake-test-secret\n", "")) as run:
            gh = c.GitHub("Stepik96/ai-documentation-quality-control", credential_user="Stepik96")
        self.assertEqual(gh.token, "fake-test-secret")
        self.assertEqual(run.call_args.args[0], ["git", "credential-manager", "get"])
        self.assertEqual(run.call_args.kwargs["env"]["GCM_INTERACTIVE"], "Never")

    def test_credential_failure_does_not_expose_output(self):
        with patch.dict(os.environ, {}, clear=True), patch("controller.run_process", return_value=subprocess.CompletedProcess([], 1, "", "private-auth-details")):
            with self.assertRaises(c.Stop) as error:
                c.GitHub("Stepik96/ai-documentation-quality-control", credential_user="Stepik96")
        self.assertNotIn("private-auth-details", str(error.exception))
