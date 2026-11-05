"""Fail-closed merge executor. GitHub strict branch protection is the atomic base barrier."""
import urllib.parse

import controller as c


def merge(gh, snapshot, result, policy):
    if policy.get("mode") != "merge" or policy.get("approved_policy_sha256") != c.policy_hash(policy):
        raise c.Stop("Merge policy has not been approved")
    if not getattr(gh, "actor", "").endswith("[bot]") or gh.actor != policy["bot_login"]:
        raise c.Stop("Merge requires the configured GitHub App")
    current = c.collect(gh, snapshot["number"], policy)
    if current is None or current["fingerprint"] != snapshot["fingerprint"]:
        raise c.Stop("Merge result obsolete")
    if c.decide(current, result, policy)[0] != "APPROVE":
        raise c.Stop("Merge criteria are not satisfied")
    base = urllib.parse.quote(policy["base"], safe="")
    # Any unavailable endpoint, including tariff/permission restrictions, stops merging.
    protection = gh.api(f"branches/{base}/protection")
    checks = protection.get("required_status_checks") or {}
    reviews = protection.get("required_pull_request_reviews") or {}
    if checks.get("strict") is not True or not protection.get("enforce_admins", {}).get("enabled"):
        raise c.Stop("Strict up-to-date protection with admin enforcement required")
    if reviews.get("dismiss_stale_reviews") is not True or reviews.get("required_approving_review_count", 0) < 1:
        raise c.Stop("Required approvals and stale-review dismissal must be enforced")
    if reviews.get("bypass_pull_request_allowances", {}).get("apps") or reviews.get("bypass_pull_request_allowances", {}).get("users") or reviews.get("bypass_pull_request_allowances", {}).get("teams"):
        raise c.Stop("Review bypass allowances are not permitted")
    protected_checks = {x["context"] for x in checks.get("checks", [])} | set(checks.get("contexts", []))
    if not protected_checks or not set(policy["required_checks"]).issubset(protected_checks):
        raise c.Stop("Required controller checks must be enforced by GitHub")
    if protection.get("required_conversation_resolution", {}).get("enabled") is not True:
        raise c.Stop("GitHub must enforce conversation resolution")
    # Refuse repositories with opaque active rulesets, including unqualified bypass actors.
    if gh.api("rulesets?includes_parents=true"):
        raise c.Stop("Additional rulesets require explicit qualification")
    comparison = gh.api(f"compare/{snapshot['base']}...{snapshot['head']}")
    if comparison.get("status") not in ("ahead", "identical") or comparison.get("behind_by") != 0:
        raise c.Stop("Reviewed head must contain the reviewed base")
    latest = {}
    for review in current["reviews"]:
        if review.get("state") in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            latest[review["user"]["login"]] = review
    if any(r["state"] == "CHANGES_REQUESTED" for r in latest.values()):
        raise c.Stop("Outstanding changes-requested review")
    own = latest.get(gh.actor, {})
    if own.get("state") != "APPROVED" or own.get("commit_id") != snapshot["head"]:
        raise c.Stop("Bot approval must reference the reviewed head")
    live = gh.api(f"pulls/{snapshot['number']}")
    target = gh.api(f"git/ref/heads/{base}")
    if target["object"]["sha"] != snapshot["base"] or live["head"]["sha"] != snapshot["head"]:
        raise c.Stop("Source or target moved before merge")
    if live.get("state") != "open" or live.get("draft") or live["base"]["ref"] != policy["base"] or live.get("mergeable_state") != "clean":
        raise c.Stop("GitHub merge state is not clean")
    # No admin/bypass flag. A concurrent base update makes the head out-of-date;
    # strict GitHub protection must reject it atomically at this endpoint.
    response = gh.api(f"pulls/{snapshot['number']}/merge", "PUT",
        {"sha": snapshot["head"], "merge_method": "squash"})
    if response.get("merged") is not True or not response.get("sha"):
        raise c.Stop("Merge not confirmed by GitHub")
    return {"status": "merged", "sha": response["sha"], "head": snapshot["head"], "base": snapshot["base"]}
