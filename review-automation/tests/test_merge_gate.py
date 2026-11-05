import copy
import unittest
from unittest.mock import patch
import controller as c
import merge_gate as m
from test_controller import fixture


class MergeGate(unittest.TestCase):
    def setUp(self):
        self.p, self.s, self.r = fixture()
        self.p.update(mode="merge", bot_login="reviewer[bot]")
        self.p["approved_policy_sha256"] = c.policy_hash(self.p)
        self.s["reviews"] = [{"user": {"login": "reviewer[bot]"}, "state": "APPROVED", "commit_id": self.s["head"]}]
        self.s["pr"]["mergeable_state"] = "clean"
        self.protection = {"required_status_checks": {"strict": True, "contexts": self.p["required_checks"]},
            "enforce_admins": {"enabled": True}, "required_pull_request_reviews": {"dismiss_stale_reviews": True, "required_approving_review_count": 1},
            "required_conversation_resolution": {"enabled": True}}
        self.target = self.s["base"]
        self.rules = []
        self.writes = []
        outer = self
        class GH:
            actor = "reviewer[bot]"
            def api(self, path, method="GET", body=None):
                if method == "PUT":
                    outer.writes.append(body)
                    return {"merged": True, "sha": "merged-sha"}
                if path.endswith("/protection"):
                    return outer.protection
                if path.startswith("rulesets"):
                    return outer.rules
                if path.startswith("compare/"):
                    return {"status": "ahead", "behind_by": 0}
                if path.startswith("git/ref"):
                    return {"object": {"sha": outer.target}}
                return outer.s["pr"]
        self.gh = GH()

    def run_merge(self):
        with patch("controller.collect", return_value=self.s):
            return m.merge(self.gh, self.s, self.r, self.p)

    def test_success_sends_expected_head(self):
        self.assertEqual(self.run_merge()["status"], "merged")
        self.assertEqual(self.writes, [{"sha": self.s["head"], "merge_method": "squash"}])

    def test_target_move_blocks(self):
        self.target = "changed"
        with self.assertRaises(c.Stop): self.run_merge()
        self.assertFalse(self.writes)

    def test_protection_missing_blocks(self):
        self.protection = {}
        with self.assertRaises(c.Stop): self.run_merge()
        self.assertFalse(self.writes)

    def test_unqualified_ruleset_blocks(self):
        self.rules = [{"id": 1}]
        with self.assertRaises(c.Stop): self.run_merge()

    def test_request_changes_blocks(self):
        self.s["reviews"].append({"user": {"login": "human"}, "state": "CHANGES_REQUESTED"})
        with self.assertRaises(c.Stop): self.run_merge()

    def test_wrong_approval_version_blocks(self):
        self.s["reviews"][0]["commit_id"] = "old"
        with self.assertRaises(c.Stop): self.run_merge()

    def test_api_error_blocks(self):
        with patch.object(self.gh, "api", side_effect=c.Stop("403")):
            with self.assertRaises(c.Stop): self.run_merge()
        self.assertFalse(self.writes)
