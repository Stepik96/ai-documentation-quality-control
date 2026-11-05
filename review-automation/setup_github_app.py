"""Local official GitHub manifest flow. User creates/installs App in browser."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import html
import json
import secrets
import time
from urllib.parse import parse_qs, urlparse
import webbrowser

import controller as c
from github_app import load_secret, save_secret


def main():
    state = secrets.token_urlsafe(32)
    target = c.ROOT / ".state" / "github-app.dpapi"
    if target.exists():
        raise c.Stop("GitHub App already configured; refusing to replace its key")
    server = HTTPServer(("127.0.0.1", 0), Handler)
    server.timeout = 1
    server.state = state
    server.done = False
    server.target = target
    server.base = f"http://127.0.0.1:{server.server_port}"
    c.write_json(c.ROOT / ".state" / "setup-link.json", {"url": server.base + "/?state=" + state})
    server.manifest = {
        "name": "AI Documentation Reviewer " + secrets.token_hex(3),
        "url": "https://github.com/Stepik96/ai-documentation-quality-control",
        "description": "Local Codex PR review. No merge or repository write permission.",
        "public": False,
        "hook_attributes": {"url": "https://github.com/Stepik96/ai-documentation-quality-control", "active": False},
        "redirect_url": server.base + "/manifest",
        "setup_url": server.base + "/installed?state=" + state,
        "default_permissions": {"contents": "read", "issues": "read", "checks": "read", "statuses": "read", "pull_requests": "write"},
        "default_events": []
    }
    print("Local GitHub App setup opened in browser. Create and install only on the project repository.", flush=True)
    webbrowser.open(server.base + "/?state=" + state)
    deadline = time.monotonic() + 3600
    while not server.done and time.monotonic() < deadline:
        server.handle_request()
    server.server_close()
    if not server.done:
        raise c.Stop("GitHub App setup timed out; no publication enabled")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Callback codes and state are never printed.

    def page(self, body, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(("<!doctype html><html><meta charset='utf-8'><title>GitHub reviewer setup</title>" + body).encode())

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
            self.page("Invalid host", 400)
            return
        if not secrets.compare_digest(query.get("state", [""])[0], self.server.state):
            self.page("Invalid or expired setup state", 403)
            return
        if parsed.path == "/":
            manifest = html.escape(json.dumps(self.server.manifest), quote=True)
            self.page("<h1>Отдельный GitHub reviewer</h1><p>Создайте приватный GitHub App. "
                "Права: чтение contents/issues/checks/statuses, запись pull requests. "
                "Нет записи содержимого репозитория, administration или merge.</p>"
                "<p>После создания установите App только на ai-documentation-quality-control. "
                "Публикация review останется выключенной до итогового подтверждения.</p>"
                f"<form action='https://github.com/settings/apps/new?state={self.server.state}' method='post'>"
                f"<input type='hidden' name='manifest' value='{manifest}'>"
                "<button type='submit'>Перейти к созданию GitHub App</button></form>")
        elif parsed.path == "/manifest":
            code = query.get("code", [""])[0]
            if not code or not all(x.isalnum() or x in "-_" for x in code):
                self.page("Invalid manifest code", 400)
                return
            try:
                # Public official endpoint. No user credential or OAuth token extraction.
                gh = c.GitHub("Stepik96/ai-documentation-quality-control", credential_user="Stepik96")
                app = gh.request(f"/app-manifests/{code}/conversions", "POST", {})
                save_secret(self.server.target, {"id": app["id"], "client_id": app["client_id"], "slug": app["slug"], "pem": app["pem"]})
                self.page("<h1>App создан</h1><p>Ключ сохранён локально, зашифрован Windows DPAPI. "
                    "Теперь установите App только на репозиторий проекта.</p>"
                    f"<a href='https://github.com/apps/{html.escape(app['slug'], quote=True)}/installations/new'>Установить GitHub App</a>")
                print("GitHub App created; awaiting repository installation.", flush=True)
            except (c.Stop, KeyError, OSError):
                self.page("Setup failed. No secrets printed; publication remains disabled.", 500)
        elif parsed.path == "/installed":
            value = query.get("installation_id", [""])[0]
            if not value.isdigit() or not self.server.target.exists():
                self.page("Invalid installation", 400)
                return
            secret = load_secret(self.server.target)
            secret["installation_id"] = int(value)
            save_secret(self.server.target, secret)
            policy = c.read_json(c.ROOT / "policy.json")
            policy["github_app_config"] = ".state/github-app.dpapi"
            policy["bot_login"] = secret["slug"] + "[bot]"
            policy["mode"] = "dry-run"
            policy["approved_policy_sha256"] = ""
            c.write_json(c.ROOT / "policy.json", policy)
            self.page("<h1>Подключение завершено</h1><p>Можно вернуться в Codex. Review и merge не включены.</p>")
            print("GitHub App installation saved. Mode remains dry-run.", flush=True)
            self.server.done = True
        else:
            self.page("Not found", 404)


if __name__ == "__main__":
    main()
