import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import controller as c


def fixture():
    p = c.read_json(c.ROOT / "policy.json")
    p["allowed_authors"] = ["developer"]
    pr = {"number": 7, "state": "open", "draft": False, "title": "Docs", "body": "Closes #3",
          "head": {"sha": "a" * 40, "repo": {"full_name": p["repository"]}},
          "base": {"sha": "b" * 40, "ref": "main"}, "user": {"login": "developer"},
          "mergeable": True, "changed_files": 1}
    s = {"repository": p["repository"], "number": 7, "head": "a" * 40, "base": "b" * 40,
         "pr": pr, "files": [{"filename": "docs/guide.md", "patch": "@@ -1 +1 @@\n-old\n+new", "status": "modified"}],
         "issues": [{"number": 3, "body": "## Критерии готовности\n- [ ] Уточнить руководство\n"}],
         "criteria": [{"id": "3:1", "requirement": "Уточнить руководство"}],
         "checks": [{"name": "review-controller-tests", "status": "completed", "conclusion": "success"}],
         "statuses": [], "comments": [], "reviews": [], "inline_comments": [],
         "documents_from_base": {"README.md": "План"}, "head_contents": {"docs/guide.md": "new\n"}}
    s["fingerprint"] = c.context_fingerprint(s)
    r = {k: s[k] for k in ("repository", "number", "head", "base")}
    r.update(risk="low", recommendation="no_concerns_found",
        criteria=[{"id": "3:1", "status": "fulfilled", "evidence": "docs/guide.md:1", "remaining": ""}],
        findings=[], questions=[], previous_findings=[], coverage={"complete": True, "unavailable": ["Приложения нет"]})
    return p, s, r


class FakeGitHub:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.repo = snapshot["repository"]
        self.writes = []

    def pages(self, endpoint, key=None):
        s = self.snapshot
        if endpoint.startswith("pulls?"):
            return [s["pr"]]
        if endpoint == "pulls/7/files":
            return s["files"]
        if endpoint.endswith("/check-runs"):
            return s["checks"]
        if endpoint.endswith("/statuses"):
            return s["statuses"]
        if endpoint == "pulls/7/reviews":
            return s["reviews"]
        if endpoint == "issues/7/comments":
            return s["comments"]
        if endpoint == "pulls/7/comments":
            return s["inline_comments"]
        raise AssertionError(endpoint)

    def api(self, endpoint, method="GET", body=None):
        if method != "GET":
            self.writes.append((endpoint, method, body))
            self.snapshot["reviews"].append({"user": {"login": "bot"}, "body": body["body"]})
            return {"id": 1}
        if endpoint == "pulls/7":
            return self.snapshot["pr"]
        if endpoint == "issues/3":
            return self.snapshot["issues"][0]
        raise AssertionError(endpoint)

    def request(self, path):
        assert path == "/user"
        return {"login": "bot"}

    def file(self, path, ref):
        return self.snapshot["head_contents"].get(path, "План")


def agent_for(result):
    def analyze(snapshot, previous, policy):
        r = copy.deepcopy(result)
        r["criteria"] = [{"id": x["id"], "status": "fulfilled", "evidence": "docs/guide.md:1", "remaining": ""} for x in snapshot["criteria"]]
        return r
    return analyze


class Decisions(unittest.TestCase):
    def setUp(self):
        self.p, self.s, self.r = fixture()

    def decision(self):
        return c.decide(self.s, self.r, self.p)[0]

    def test_correct_documentation(self):
        self.assertEqual(self.decision(), "APPROVE")

    def finding(self):
        return {"id": "F1", "severity": "P1", "title": "Исходник удаляется", "file": "docs/guide.md", "line": 1,
                "trigger": "После запуска", "expected": "Сохранён", "actual": "Удалён", "impact": "Потеря файла",
                "fix": "Сохранить исходник", "verification": "Проверить скачивание"}

    def test_confirmed_bug(self):
        self.r["findings"] = [self.finding()]
        self.assertEqual(self.decision(), "REQUEST_CHANGES")

    def test_unfulfilled_task(self):
        self.r["criteria"][0]["status"] = "not_fulfilled"
        self.assertEqual(self.decision(), "REQUEST_CHANGES")

    def test_documentation_contradiction(self):
        self.r["findings"] = [self.finding() | {"title": "V2 описана как готовая V1", "severity": "P2"}]
        self.assertEqual(self.decision(), "REQUEST_CHANGES")

    def test_missing_requirements_for_behavior(self):
        self.s["files"][0]["filename"] = "src/api.py"
        self.s["issues"] = []
        self.s["criteria"] = []
        self.r["criteria"] = []
        self.assertEqual(self.decision(), "HUMAN")

    def test_failed_test(self):
        self.s["checks"][0]["conclusion"] = "failure"
        self.assertEqual(self.decision(), "HUMAN")

    def test_absent_ci(self):
        self.s["checks"] = []
        self.assertEqual(self.decision(), "HUMAN")

    def test_duplicate_ci_context(self):
        self.s["checks"] *= 2
        self.assertEqual(self.decision(), "HUMAN")

    def test_unverified(self):
        self.r["criteria"][0]["status"] = "unverified"
        self.assertEqual(self.decision(), "HUMAN")

    def test_rule_change_inside_pr(self):
        self.s["files"][0]["filename"] = "review-automation/rules.md"
        self.assertEqual(self.decision(), "HUMAN")

    def test_renaming_sensitive_file(self):
        self.s["files"][0]["previous_filename"] = "AGENTS.md"
        self.assertEqual(self.decision(), "HUMAN")

    def test_fork(self):
        self.s["pr"]["head"]["repo"]["full_name"] = "outsider/fork"
        self.assertEqual(self.decision(), "HUMAN")

    def test_unknown_author(self):
        self.p["allowed_authors"] = []
        self.assertEqual(self.decision(), "HUMAN")

    def test_invented_criteria(self):
        self.r["criteria"][0]["id"] = "fake"
        with self.assertRaises(c.Stop):
            self.decision()

    def test_invalid_agent_response(self):
        with self.assertRaises(c.Stop):
            c.validate({"decision": "approve"}, self.s)

    def test_invalid_line(self):
        self.r["findings"] = [self.finding() | {"line": 99}]
        with self.assertRaises(c.Stop):
            self.decision()

    def test_wrong_head(self):
        self.r["head"] = "old"
        with self.assertRaises(c.Stop):
            self.decision()

    def test_base_changes_fingerprint(self):
        old = c.context_fingerprint(self.s)
        self.s["base"] = "c" * 40
        self.assertNotEqual(old, c.context_fingerprint(self.s))

    def test_issue_edit_changes_fingerprint(self):
        old = c.context_fingerprint(self.s)
        self.s["issues"][0]["body"] += "new criterion"
        self.assertNotEqual(old, c.context_fingerprint(self.s))

    def test_doc_criteria_without_task(self):
        self.s["pr"]["body"] = ""
        collected = c.collect(FakeGitHub(self.s), 7, self.p)
        self.assertEqual(len(collected["criteria"]), 4)

    def test_draft_skipped(self):
        self.s["pr"]["draft"] = True
        self.assertIsNone(c.collect(FakeGitHub(self.s), 7, self.p))

    def test_merge_always_disabled(self):
        self.p["mode"] = "merge"
        with self.assertRaises(c.Stop):
            c.publish(FakeGitHub(self.s), self.s, self.r, self.p, "key", "report")

    def test_no_credentials(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(c.Stop):
            c.GitHub(self.p["repository"])


class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.p, self.s, self.r = fixture()
        self.gh = FakeGitHub(self.s)
        self.temp = tempfile.TemporaryDirectory()
        self.state = c.State(self.temp.name)

    def tearDown(self):
        self.state.db.close()
        self.temp.cleanup()

    def run_cycle(self, analyze=None):
        return c.run_once(self.gh, self.state, self.p, analyze or agent_for(self.r))

    def test_full_local_cycle_no_duplicate(self):
        self.assertEqual(len(self.run_cycle()), 1)
        self.assertEqual(self.run_cycle(), [])
        self.assertEqual(self.gh.writes, [])
        artifact = list(Path(self.temp.name).glob("*.json"))[0]
        self.assertEqual(c.read_json(artifact)["publication"], "dry-run")

    def test_new_commit_rechecks(self):
        self.run_cycle()
        self.s["head"] = self.s["pr"]["head"]["sha"] = "c" * 40
        self.r["head"] = self.s["head"]
        self.assertEqual(len(self.run_cycle()), 1)

    def test_previous_finding_fix(self):
        finding = Decisions().finding()
        self.r["findings"] = [finding]
        self.assertEqual(self.run_cycle()[0]["decision"], "REQUEST_CHANGES")
        self.s["head"] = self.s["pr"]["head"]["sha"] = "c" * 40
        self.r["head"] = self.s["head"]
        self.r["findings"] = []
        def fixed(snapshot, previous, policy):
            self.assertEqual(previous["findings"][0]["id"], "F1")
            result = agent_for(self.r)(snapshot, previous, policy)
            result["previous_findings"] = ["F1 исправлено: исходник сохраняется"]
            return result
        self.assertEqual(self.run_cycle(fixed)[0]["decision"], "APPROVE")

    def test_commit_during_analysis(self):
        def stale(snapshot, previous, policy):
            self.s["pr"]["head"]["sha"] = "c" * 40
            return agent_for(self.r)(snapshot, previous, policy)
        with self.assertRaises(c.Stop):
            self.run_cycle(stale)
        self.assertEqual(self.gh.writes, [])

    def test_agent_error_quota_auth_bounded(self):
        calls = []
        def broken(*args):
            calls.append(True)
            raise c.Stop("Simulated quota/auth failure")
        for _ in range(2):
            with self.assertRaises(c.Stop):
                self.run_cycle(broken)
        self.assertEqual(self.run_cycle(broken), [])
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.gh.writes, [])

    def test_invalid_response_no_publication(self):
        with self.assertRaises(c.Stop):
            self.run_cycle(lambda *args: {"approved": True})
        self.assertEqual(self.gh.writes, [])

    def test_stop_during_analysis(self):
        def stopped(snapshot, previous, policy):
            (Path(self.temp.name) / "STOP").touch()
            return agent_for(self.r)(snapshot, previous, policy)
        with self.assertRaises(c.Stop):
            self.run_cycle(stopped)
        self.assertEqual(self.gh.writes, [])

    def test_publish_and_retry_after_lost_local_state(self):
        self.p["mode"] = "publish"
        self.p["bot_login"] = "bot"
        self.p["approved_policy_sha256"] = c.policy_hash(self.p)
        self.assertEqual(self.run_cycle()[0]["publication"], "published")
        self.state.db.execute("DELETE FROM runs")
        self.state.db.commit()
        self.run_cycle()
        self.assertEqual(len(self.gh.writes), 1)

    def test_policy_changed_invalidates_consent(self):
        self.p["mode"] = "publish"
        self.p["bot_login"] = "bot"
        self.p["approved_policy_sha256"] = "not-the-policy-hash"
        with self.assertRaises(c.Stop):
            self.run_cycle()
        self.assertEqual(self.gh.writes, [])


if __name__ == "__main__":
    unittest.main()
