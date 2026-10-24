"""B11 functional verification: DB user login, role gating, audit persistence.

Run while the functional BFF (port 8021, DATABASE_URL=sqlite:///./b11-functional.db,
AUTH_ENABLED=true) is up. Exit 0 only when every check passes.
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

out = open("b11-functional.log", "w", encoding="utf-8")
cookies: dict[str, str] = {}


def call(method, path, body=None, base="http://127.0.0.1:8021"):
    req = Request(f"{base}{path}",
                  data=json.dumps(body).encode() if body is not None else None,
                  method=method,
                  headers={"Content-Type": "application/json", **cookie_header()})
    try:
        with urlopen(req, timeout=20) as resp:
            _capture_cookies(resp)
            return resp.status, json.loads(resp.read().decode() or "{}")
    except HTTPError as exc:
        _capture_cookies(exc)
        try:
            return exc.code, json.loads(exc.read().decode() or "{}")
        except ValueError:
            return exc.code, {}


def _capture_cookies(resp) -> None:
    for header_value in resp.headers.get_all("Set-Cookie") or []:
        name_value = header_value.split(";")[0]
        name, _, value = name_value.partition("=")
        if name.strip() and value.strip():
            cookies[name.strip()] = value.strip()


def cookie_header() -> dict:
    return {"Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items())} if cookies else {}


def check(name, ok, detail):
    out.write(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}\n")
    return ok


ok = True

db_url = f"sqlite:///{Path(__file__).resolve().parent.joinpath('b11-functional.db').as_posix()}"
cli_env = {**os.environ, "DATABASE_URL": db_url}


def cli_create(username: str, role: str, password: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [r".venv\Scripts\python.exe", r"..\scripts\manage_users.py", "create", username,
         "--role", role, "--password-stdin"],
        input=f"{password}\n", capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=cli_env)


# 1. real database users via the management CLI (idempotent re-run tolerated)
cli = cli_create("b11-tester", "analyst", "b11-Str0ng!pass")
ok &= check("manage_users_create_analyst",
            cli.returncode == 0 or "user already exists" in (cli.stdout + cli.stderr),
            (cli.stdout + cli.stderr).strip()[:160])
cli2 = cli_create("b11-operator", "operator", "b11-Op3rator!pw")
ok &= check("manage_users_create_operator",
            cli2.returncode == 0 or "user already exists" in (cli2.stdout + cli2.stderr),
            (cli2.stdout + cli2.stderr).strip()[:160])

# 2. login with the real database user
status, login = call("POST", "/api/auth/login", {"username": "b11-tester", "password": "b11-Str0ng!pass"})
ok &= check("db_user_login", status == 200 and login.get("user", {}).get("source") == "database",
            f"HTTP {status} source={login.get('user', {}).get('source')} role={login.get('user', {}).get('role')}")
out.write(f"cookies captured: {sorted(cookies)}\n")

# 3. session cookie works for an authenticated read
status, me = call("GET", "/api/auth/me")
ok &= check("authenticated_me", status == 200 and (me.get("user") or {}).get("username") == "b11-tester",
            f"HTTP {status} username={(me.get('user') or {}).get('username')}")

# 4. wrong password rejected
status, _bad = call("POST", "/api/auth/login", {"username": "b11-tester", "password": "wrong"})
ok &= check("wrong_password_rejected", status == 401, f"HTTP {status}")

# 5. authenticated system settings expose persistence state
status, settings_body = call("GET", "/api/system/settings")
ok &= check("system_settings_with_auth",
            status == 200 and settings_body.get("auth_enabled") is True
            and settings_body.get("audit_persisted") is True,
            f"HTTP {status} auth_enabled={settings_body.get('auth_enabled')} "
            f"audit_persisted={settings_body.get('audit_persisted')}")

# 6. analyst is denied the audit route (role gating on a real DB user)
status, denied = call("GET", "/api/audit/events")
ok &= check("analyst_denied_audit", status == 403 and denied.get("detail", {}).get("error") == "PERMISSION_DENIED",
            f"HTTP {status} error={denied.get('detail', {}).get('error')}")

# 7. operator reads persisted audit events through the API
cookies.clear()
status, op_login = call("POST", "/api/auth/login", {"username": "b11-operator", "password": "b11-Op3rator!pw"})
ok &= check("operator_login", status == 200 and op_login.get("user", {}).get("role") == "operator",
            f"HTTP {status} role={op_login.get('user', {}).get('role')}")
status, audit = call("GET", "/api/audit/events")
ok &= check("operator_reads_persisted_audit", status == 200 and audit.get("persisted") is True,
            f"HTTP {status} persisted={audit.get('persisted')} total={audit.get('total')}")

out.close()
sys.exit(0 if ok else 1)
