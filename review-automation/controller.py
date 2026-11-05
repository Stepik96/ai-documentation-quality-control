"""Trusted local PR controller. Never checks out or executes PR code. Python 3.12+."""
from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent


class Stop(RuntimeError):
    """Fail closed; safe reason, without subprocess output or credentials."""


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def run_process(command, *, input=None, timeout, env=None, cwd=None, **unused):
    """Bound a CLI invocation and its child process tree, including npm .cmd launchers."""
    options = {"start_new_session": True} if os.name != "nt" else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    process = subprocess.Popen(command, stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", env=env, cwd=cwd, **options)
    try:
        stdout, stderr = process.communicate(input, timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            taskkill = str(Path(os.environ["SYSTEMROOT"]) / "System32/taskkill.exe")
            subprocess.run([taskkill, "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
        else:
            import signal
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
        process.kill()
        process.communicate(timeout=10)
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


class GitHub:
    def __init__(self, repo, token=None):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            raise Stop("Invalid repository")
        self.repo = repo
        self.token = token or os.environ.get("REVIEW_GITHUB_TOKEN")
        if not self.token:
            raise Stop("GitHub authorization unavailable: set REVIEW_GITHUB_TOKEN locally")

    def request(self, path, method="GET", body=None):
        # Relative endpoint only; credentials never follow redirects to another host.
        if not path.startswith("/") or ".." in path or "://" in path:
            raise Stop("Invalid GitHub endpoint")
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        req = urllib.request.Request("https://api.github.com" + path,
            data=None if body is None else json.dumps(body).encode(), method=method,
            headers={"Authorization": "Bearer " + self.token, "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "local-codex-review"})
        try:
            with urllib.request.build_opener(NoRedirect()).open(req, timeout=30) as response:
                raw = response.read(4_000_001)
                if len(raw) > 4_000_000:
                    raise Stop("GitHub response too large")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            raise Stop(f"GitHub HTTP {error.code}; no action performed or confirmed") from None
        except (OSError, ValueError):
            raise Stop("GitHub network or response error") from None

    def api(self, endpoint, method="GET", body=None):
        return self.request(f"/repos/{self.repo}/{endpoint}", method, body)

    def pages(self, endpoint, key=None):
        result = []
        separator = "&" if "?" in endpoint else "?"
        for page in range(1, 51):
            response = self.api(f"{endpoint}{separator}per_page=100&page={page}")
            rows = response[key] if key else response
            result.extend(rows)
            if len(rows) < 100:
                return result
        raise Stop("Pagination limit reached; incomplete context")

    def file(self, path, ref):
        data = self.api("contents/" + urllib.parse.quote(path, safe="/") + "?ref=" + ref)
        if data.get("encoding") != "base64" or data.get("size", 0) > 150000:
            raise Stop("Unsupported or oversized context file")
        try:
            return base64.b64decode(data["content"]).decode("utf-8")
        except (ValueError, UnicodeError):
            raise Stop("Context file is not valid UTF-8") from None


def issue_numbers(body):
    # Deliberately only same-repository closing references; no arbitrary URL fetches.
    return sorted(set(int(x) for x in re.findall(
        r"(?i)\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)\b", body or "")))


def acceptance(issues):
    criteria = []
    for issue in issues:
        # Criteria must be explicitly separated from implementation checklist.
        section = re.search(r"(?ims)^##\s+(?:Критерии готовности|Acceptance criteria)\s*\n(.*?)(?=^##\s|\Z)", issue.get("body") or "")
        if section:
            for index, line in enumerate(re.findall(r"(?m)^\s*-\s+\[[ xX]\]\s+(.+)$", section[1]), 1):
                criteria.append({"id": f"{issue['number']}:{index}", "requirement": line})
    return criteria


DOC_CRITERIA = [
    {"id": "doc:1", "requirement": "Документация соответствует границам задачи и действующему scope"},
    {"id": "doc:2", "requirement": "Планируемые возможности отделены от реализованных"},
    {"id": "doc:3", "requirement": "Ссылки, термины и структура изменённых материалов согласованы"},
    {"id": "doc:4", "requirement": "Нет несогласованного изменения требований или сокрытия противоречий"},
]


def docs_only(files):
    return bool(files) and all(f["filename"].endswith(".md") and
        (f["filename"].startswith("docs/") or f["filename"] == "README.md") for f in files)


def collect(gh, number, policy):
    pr = gh.api(f"pulls/{number}")
    if pr["state"] != "open" or pr["draft"] or pr["base"]["ref"] != policy["base"]:
        return None
    head, base = pr["head"]["sha"], pr["base"]["sha"]
    files = gh.pages(f"pulls/{number}/files")
    if len(files) != pr["changed_files"]:
        raise Stop("Incomplete changed file list")
    issues = [gh.api(f"issues/{n}") for n in issue_numbers(pr.get("body"))]
    criteria = acceptance(issues)
    if docs_only(files):
        criteria += DOC_CRITERIA
    checks = gh.pages(f"commits/{head}/check-runs", "check_runs")
    statuses = gh.pages(f"commits/{head}/statuses")
    comments = gh.pages(f"issues/{number}/comments")
    reviews = gh.pages(f"pulls/{number}/reviews")
    inline = gh.pages(f"pulls/{number}/comments")
    threads = None  # REST lacks authoritative resolved-state; merge requires GraphQL below.
    documents = {p: gh.file(p, base) for p in policy["trusted_docs"]}
    contents = {}
    for file in files:
        # Binary, missing/truncated patch and oversized PR => human; never pretend full coverage.
        if file["status"] != "removed" and file.get("patch") is not None:
            try:
                contents[file["filename"]] = gh.file(file["filename"], head)
            except Stop:
                contents[file["filename"]] = None
    snapshot = {"repository": gh.repo, "number": number, "head": head, "base": base,
        "pr": pr, "files": files, "issues": issues, "criteria": criteria,
        "checks": checks, "statuses": statuses, "comments": comments,
        "reviews": reviews, "inline_comments": inline, "threads": threads,
        "documents_from_base": documents, "head_contents": contents}
    snapshot["bot_login"] = policy["bot_login"]
    snapshot["fingerprint"] = context_fingerprint(snapshot)
    if len(json.dumps(snapshot, ensure_ascii=False).encode()) > policy["max_context_bytes"]:
        raise Stop("Context exceeds budget; manual review required (no truncation)")
    return snapshot


def context_fingerprint(snapshot):
    # Exclude own publications from version identity; include task edits, CI and human discussion.
    context = {k: snapshot[k] for k in ("repository", "number", "head", "base", "files", "issues", "criteria", "checks", "statuses", "documents_from_base")}
    context["pr"] = {k: snapshot["pr"].get(k) for k in ("title", "body", "draft", "state", "head", "base", "user")}
    # The report marker alone cannot suppress human discussion: exclude only configured bot.
    bot = snapshot.get("bot_login", "")
    for key in ("comments", "reviews", "inline_comments"):
        context[key] = [x for x in snapshot.get(key, []) if x.get("user", {}).get("login") != bot]
    return digest(context)


def validate(result, snapshot):
    expected = {"repository", "number", "head", "base", "risk", "recommendation", "criteria", "findings", "questions", "previous_findings", "coverage"}
    if not isinstance(result, dict) or set(result) != expected:
        raise Stop("Invalid agent result fields")
    for key in ("repository", "number", "head", "base"):
        if result[key] != snapshot[key]:
            raise Stop("Agent result is for a different PR version")
    if result["risk"] not in ("low", "medium", "high") or result["recommendation"] not in ("no_concerns_found", "needs_review", "changes_required"):
        raise Stop("Invalid agent decision")
    if not all(isinstance(result[k], list) for k in ("criteria", "findings", "questions", "previous_findings")):
        raise Stop("Invalid agent lists")
    ids = [c.get("id") for c in result["criteria"] if isinstance(c, dict)]
    if len(ids) != len(result["criteria"]) or len(set(ids)) != len(ids) or set(ids) != {c["id"] for c in snapshot["criteria"]}:
        raise Stop("Criteria missing, duplicated or invented")
    for criterion in result["criteria"]:
        if set(criterion) != {"id", "status", "evidence", "remaining"} or criterion["status"] not in ("fulfilled", "not_fulfilled", "unverified", "not_applicable"):
            raise Stop("Invalid criterion status")
        if not isinstance(criterion["evidence"], str) or not isinstance(criterion["remaining"], str):
            raise Stop("Invalid criterion evidence")
        if criterion["status"] == "fulfilled" and not criterion["evidence"].strip():
            raise Stop("Fulfilled criterion has no evidence")
    for finding in result["findings"]:
        if set(finding) != {"id", "severity", "title", "file", "line", "trigger", "expected", "actual", "impact", "fix", "verification"}:
            raise Stop("Invalid finding shape")
        if finding["severity"] not in ("P0", "P1", "P2", "suggestion"):
            raise Stop("Invalid severity")
        if not all(isinstance(finding[k], str) and finding[k].strip() for k in ("id", "title", "trigger", "expected", "actual", "impact", "fix", "verification")):
            raise Stop("Finding lacks concrete explanation")
        if finding["file"] is not None:
            if finding["file"] not in {f["filename"] for f in snapshot["files"]}:
                raise Stop("Finding file not in PR")
        if finding["line"] is not None:
            lines = snapshot["head_contents"].get(finding["file"])
            if type(finding["line"]) is not int or not lines or not 1 <= finding["line"] <= len(lines.splitlines()):
                raise Stop("Invalid finding line")
    if not all(isinstance(q, str) for q in result["questions"] + result["previous_findings"]) or not isinstance(result["coverage"], dict):
        raise Stop("Invalid coverage or questions")
    if set(result["coverage"]) != {"complete", "unavailable"} or type(result["coverage"]["complete"]) is not bool or not isinstance(result["coverage"]["unavailable"], list) or not all(isinstance(x, str) for x in result["coverage"]["unavailable"]):
        raise Stop("Invalid coverage")
    return result


def check_states(snapshot, required):
    # Duplicate contexts are ambiguous, not silently overwritten.
    states = {}
    for check in snapshot["checks"]:
        states.setdefault(check["name"], []).append(check["conclusion"] if check["status"] == "completed" else "pending")
    # Status API is newest-first; repeated statuses for the same context are normal.
    latest = {}
    for status in snapshot["statuses"]:
        latest.setdefault(status["context"], status["state"])
    for name, state in latest.items():
        states.setdefault(name, []).append(state)
    if not required:
        return False
    return all(states.get(name) == ["success"] for name in required) and all(
        all(s in ("success", "neutral", "skipped") for s in values) for values in states.values())


def decide(snapshot, result, policy):
    validate(result, snapshot)
    blockers = [f for f in result["findings"] if f["severity"] in ("P0", "P1", "P2")]
    if blockers or any(c["status"] == "not_fulfilled" for c in result["criteria"]):
        return "REQUEST_CHANGES", ["Подтверждённая ошибка или невыполненный критерий задачи"]
    reasons = []
    pr = snapshot["pr"]
    if not result["coverage"]["complete"] or any(f.get("patch") is None for f in snapshot["files"]):
        reasons.append("Неполное покрытие изменений")
    if any(v is None for v in snapshot["head_contents"].values()):
        reasons.append("Не прочитаны изменённые файлы")
    if not snapshot["criteria"] or any(c["status"] in ("unverified", "not_applicable") for c in result["criteria"]):
        reasons.append("Критерии не подтверждены полностью")
    if not docs_only(snapshot["files"]) and not acceptance(snapshot["issues"]):
        reasons.append("Для изменения поведения нужна связанная задача с критериями")
    if result["questions"] or result["risk"] != "low" or result["recommendation"] != "no_concerns_found":
        reasons.append("Нужна оценка человека")
    if not check_states(snapshot, policy["required_checks"]):
        reasons.append("CI отсутствует, неоднозначен или не завершён успешно")
    paths = [p for f in snapshot["files"] for p in (f["filename"], f.get("previous_filename", f["filename"]))]
    if any(any(p.casefold().startswith(prefix.casefold()) for prefix in policy["human_paths"]) for p in paths):
        reasons.append("Изменены правила, требования, автоматизация или чувствительные файлы")
    if pr["head"]["repo"] is None or pr["head"]["repo"]["full_name"] != policy["repository"]:
        reasons.append("PR из внешнего источника")
    if pr["user"]["login"] not in policy["allowed_authors"]:
        reasons.append("Автор не входит в разрешённый список")
    if pr.get("mergeable") is not True:
        reasons.append("Есть конфликт или состояние слияния неизвестно")
    if not docs_only(snapshot["files"]) or "documentation" not in policy["merge_categories"]:
        reasons.append("Категория не разрешена для merge")
    return ("HUMAN", reasons) if reasons else ("APPROVE", [])


def render(snapshot, result, decision, reasons, key):
    # All findings are general review text. No invented inline diff coordinates.
    statuses = {"fulfilled": "выполнено", "not_fulfilled": "не выполнено", "unverified": "не удалось проверить", "not_applicable": "неприменимо"}
    lines = [f"<!-- local-codex-review:{key} -->", f"Проверка PR #{snapshot['number']}: {decision}",
             f"Исходная версия: `{snapshot['head']}`; целевая: `{snapshot['base']}`.",
             "Проверка чтением кода и документации; код PR локально не запускался."]
    criteria = {c["id"]: c["requirement"] for c in snapshot["criteria"]}
    for c in result["criteria"]:
        lines.append(f"\n- {criteria[c['id']]} — **{statuses[c['status']]}**. Подтверждение: {c['evidence']}. Осталось: {c['remaining']}")
    for f in result["findings"]:
        lines.extend([f"\n### [{f['severity']}] {f['title']}", f"Файл: {f['file'] or 'общее замечание'}; строка: {f['line'] or 'не указана'}."])
        for key_name, label in (("trigger", "Условие"), ("expected", "Ожидалось"), ("actual", "Фактически"), ("impact", "Последствия"), ("fix", "Изменить"), ("verification", "Проверка исправления")):
            lines.append(f"{label}: {f[key_name]}")
    lines += ["\nНужное решение: " + r for r in reasons + result["questions"]]
    lines.append("\nПредыдущие замечания: " + json.dumps(result["previous_findings"], ensure_ascii=False))
    lines.append("\nНедоступные проверки: " + json.dumps(result["coverage"]["unavailable"], ensure_ascii=False))
    text = "\n".join(lines)
    if len(text) > 50000:
        raise Stop("Review exceeds publication budget")
    return text


def codex_analyze(snapshot, previous, policy):
    executable = shutil.which("codex.exe") or shutil.which("codex.cmd") or shutil.which("codex")
    if not executable or executable.endswith(".ps1"):
        raise Stop("Codex executable unavailable; install official CLI with codex.cmd on PATH")
    # No GitHub authority/API keys inherited by analyzer. No checkout, hooks or repo instructions.
    environment = {k: v for k, v in os.environ.items() if k.upper() in {
        "SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "TEMP", "TMP", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "HOME", "CODEX_HOME"}}
    environment["NO_COLOR"] = "1"
    try:
        login = run_process([executable, "login", "status"], capture_output=True,
            text=True, encoding="utf-8", env=environment, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise Stop("Codex login status unavailable") from None
    if login.returncode != 0:
        raise Stop("Codex is not logged in; run codex login locally")
    with tempfile.TemporaryDirectory(prefix="codex-pr-review-") as directory:
        directory = Path(directory)
        output = directory / "result.json"
        prompt = (ROOT / "rules.md").read_text(encoding="utf-8")
        # Actual upstream prompt prefix is used, not merely cited. Stop before YAML-specific contract.
        import tomllib
        upstream = tomllib.loads((ROOT / "vendor/pr-agent/pr_agent/settings/pr_reviewer_prompts.toml").read_text(encoding="utf-8"))["pr_review_prompt"]["system"]
        prefix = upstream[upstream.index("You are PR-Reviewer"):upstream.index("{%- if extra_instructions %}")]
        prompt += "\nPR-Agent review guidance (diff format is unified diff):\n" + prefix.replace("{{ diff_hunk_format }}", "unified diff")
        prompt += "\nReturn JSON according to the provided schema.\nUNTRUSTED_DATA_JSON:\n" + json.dumps({"snapshot": snapshot, "previous_local": previous}, ensure_ascii=False)
        command = [executable, "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral",
            "--skip-git-repo-check", "--sandbox", "read-only", "--json", "--color", "never",
            "--disable", "shell_tool", "--disable", "unified_exec", "--disable", "apply_patch_freeform",
            "--disable", "multi_agent", "--disable", "apps", "--disable", "plugins",
            "--disable", "remote_plugin", "--disable", "hooks", "--disable", "browser_use",
            "--disable", "computer_use", "--disable", "in_app_browser", "--disable", "image_generation",
            "--disable", "code_mode", "--disable", "code_mode_host", "--disable", "goals",
            "-c", "agents.enabled=false", "-c", "skills.include_instructions=false",
            "-c", "skills.bundled.enabled=false", "-c", "plugins._default.enabled=false",
            "-c", 'web_search="disabled"', "-c", "tools.view_image=false", "-c", 'forced_login_method="chatgpt"',
            "--output-schema", str(ROOT / "result.schema.json"), "-o", str(output), "-"]
        try:
            process = run_process(command, input=prompt, text=True, encoding="utf-8", capture_output=True,
                cwd=directory, env=environment, timeout=policy["timeout_seconds"], check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise Stop("Codex unavailable or timed out; no decision") from None
        # Never write raw stdout/stderr to logs; may contain private input or provider details.
        if process.returncode != 0 or not output.exists():
            raise Stop("Codex failed (authorization, quota, configuration or provider); inspect CLI locally")
        completed = False
        for line in process.stdout.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                raise Stop("Malformed Codex event stream") from None
            item = event.get("item", {})
            if event.get("type") in ("turn.failed", "error"):
                raise Stop("Codex reported failure; no decision")
            completed = completed or event.get("type") == "turn.completed"
            if item.get("type") in ("command_execution", "mcp_tool_call", "web_search", "file_change"):
                raise Stop("Analyzer attempted tool use; security qualification required")
        if not completed:
            raise Stop("Codex did not confirm turn completion")
        return validate(read_json(output), snapshot)


class State:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.directory / "state.sqlite", timeout=1)
        self.db.execute("CREATE TABLE IF NOT EXISTS runs (key TEXT PRIMARY KEY, number INTEGER, attempts INTEGER, status TEXT, result TEXT)")
        self.db.commit()

    @contextlib.contextmanager
    def lock(self):
        # OS lock automatically releases after crash; no stale PID deletion race.
        path = self.directory / "controller.lock"
        with path.open("a+b") as stream:
            stream.write(b"0")
            stream.flush()
            stream.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise Stop("Another controller is running") from None
            try:
                yield
            finally:
                if os.name == "nt":
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)

    def previous(self, number):
        row = self.db.execute("SELECT result FROM runs WHERE number=? AND status='done' ORDER BY rowid DESC LIMIT 1", (number,)).fetchone()
        return json.loads(row[0]) if row else None

    def begin(self, key, number, attempts):
        row = self.db.execute("SELECT attempts,status FROM runs WHERE key=?", (key,)).fetchone()
        if row and (row[1] == "done" or row[0] >= attempts):
            return False
        self.db.execute("INSERT INTO runs VALUES (?,?,1,'running',NULL) ON CONFLICT(key) DO UPDATE SET attempts=attempts+1,status='running'", (key, number))
        self.db.commit()
        return True

    def finish(self, key, result):
        self.db.execute("UPDATE runs SET status='done',result=? WHERE key=?", (json.dumps(result, ensure_ascii=False), key))
        self.db.commit()


def policy_hash(policy):
    return digest({k: v for k, v in policy.items() if k not in ("mode", "approved_policy_sha256")})


def publish(gh, snapshot, result, policy, key, report):
    if policy["mode"] == "dry-run":
        return "dry-run"
    if policy["mode"] == "merge":
        raise Stop("Automatic merge unavailable in v1; no publication in merge mode")
    if policy["mode"] not in ("publish", "merge") or policy["approved_policy_sha256"] != policy_hash(policy):
        raise Stop("Publication not approved for this exact policy")
    identity = gh.request("/user")["login"]
    if not policy["bot_login"] or identity != policy["bot_login"] or identity == snapshot["pr"]["user"]["login"]:
        raise Stop("Independent configured reviewer identity required")
    current = collect(gh, snapshot["number"], policy)
    if current is None or current["fingerprint"] != snapshot["fingerprint"]:
        raise Stop("PR, target branch, criteria or CI changed; review obsolete")
    decision, _ = decide(current, result, policy)
    marker = f"<!-- local-codex-review:{key} -->"
    published = next((r for r in current["reviews"] if r["user"]["login"] == identity and marker in (r.get("body") or "")), None)
    if published is None:
        event = decision if decision in ("APPROVE", "REQUEST_CHANGES") else "COMMENT"
        gh.api(f"pulls/{snapshot['number']}/reviews", "POST", {"commit_id": snapshot["head"], "body": report, "event": event})
    return "published"


def run_once(gh, state, policy, analyzer=codex_analyze):
    completed = []
    with state.lock():
        for pr in gh.pages(f"pulls?state=open&base={policy['base']}"):
            if pr["draft"]:
                continue
            snapshot = collect(gh, pr["number"], policy)
            if snapshot is None:
                continue
            key = digest({"context": snapshot["fingerprint"], "policy": policy_hash(policy),
                "rules": (ROOT / "rules.md").read_text(encoding="utf-8"),
                "upstream": (ROOT / "vendor/pr-agent/pr_agent/settings/pr_reviewer_prompts.toml").read_text(encoding="utf-8"),
                "mode": policy["mode"]})
            if not state.begin(key, pr["number"], policy["max_attempts"]):
                continue
            result = analyzer(snapshot, state.previous(pr["number"]), policy)
            decision, reasons = decide(snapshot, result, policy)
            current = collect(gh, pr["number"], policy)
            if current is None or current["fingerprint"] != snapshot["fingerprint"]:
                raise Stop("Result obsolete; no publication")
            report = render(snapshot, result, decision, reasons, key)
            if (state.directory / "STOP").exists():
                raise Stop("Stop requested; no publication")
            artifact = {"key": key, "number": snapshot["number"], "head": snapshot["head"], "base": snapshot["base"],
                "decision": decision, "reasons": reasons, "checks": snapshot["checks"], "result": result,
                "publication": "pending"}
            write_json(state.directory / f"{key}.json", artifact)
            (state.directory / f"{key}.md").write_text(report, encoding="utf-8")
            artifact["publication"] = publish(gh, snapshot, result, policy, key, report)
            write_json(state.directory / f"{key}.json", artifact)
            state.finish(key, result)
            completed.append({"number": pr["number"], "decision": decision, "publication": artifact["publication"]})
    return completed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("once", "watch", "status", "stop", "resume", "doctor", "policy-hash"))
    parser.add_argument("--policy", default=str(ROOT / "policy.json"))
    parser.add_argument("--state", default=str(ROOT / ".state"))
    args = parser.parse_args()
    policy = read_json(args.policy)
    state = State(args.state)
    if args.command == "policy-hash":
        print(policy_hash(policy))
        return
    if args.command == "stop":
        (state.directory / "STOP").touch()
        print("Stop requested; current analysis may take up to its timeout to finish")
        return
    if args.command == "resume":
        (state.directory / "STOP").unlink(missing_ok=True)
        print("Stop flag cleared; run watch to start")
        return
    if args.command == "status":
        print(json.dumps(state.db.execute("SELECT number,status,attempts,key FROM runs ORDER BY rowid DESC LIMIT 20").fetchall()))
        return
    if args.command == "doctor":
        print(json.dumps({"python": True, "codex": bool(shutil.which("codex.cmd") or shutil.which("codex")),
            "github_token_set": bool(os.environ.get("REVIEW_GITHUB_TOKEN")), "mode": policy["mode"],
            "merge_available": False, "required_checks": policy["required_checks"]}, ensure_ascii=False))
        return
    try:
        gh = GitHub(policy["repository"])
        while not (state.directory / "STOP").exists():
            completed = run_once(gh, state, policy)
            if completed:
                print(json.dumps(completed, ensure_ascii=False), flush=True)
            if args.command == "once":
                return
            # Short waits permit stop responsiveness; unchanged state stays quiet.
            for _ in range(policy["poll_seconds"]):
                if (state.directory / "STOP").exists():
                    return
                time.sleep(1)
    except (Stop, ValueError, KeyError, sqlite3.Error) as error:
        safe = str(error) if isinstance(error, Stop) else "Invalid context, policy or state; stopped"
        write_json(state.directory / "last-error.json", {"time": int(time.time()), "reason": safe})
        print(safe)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
