# P0 Sync Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove repository and network exposure of synchronization credentials and ensure MTOP failures cannot persist raw response content.

**Architecture:** Keep the existing local Docker deployment and file-backed AES key. Exclude runtime data from Git, bind published ports to loopback by default, and convert parse failures to a fixed sanitized message before they reach logs or account error fields.

**Tech Stack:** Docker Compose, FastAPI/Python 3.11, pytest

---

### Task 1: Protect runtime secrets and local service ports

**Files:**
- Modify: `.gitignore`
- Modify: `docker-compose.yml`
- Create: `server/backend/test_security_baseline.py`
- Untrack without deleting: `server/backend/data/secret.key`

- [ ] **Step 1: Write the failing security baseline tests**

Create `server/backend/test_security_baseline.py` with tests that:

```python
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def test_runtime_secret_is_ignored_and_untracked():
    ignored = subprocess.run(
        ["git", "check-ignore", "server/backend/data/secret.key"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "server/backend/data/secret.key"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert ignored.returncode == 0
    assert tracked.returncode != 0


def test_compose_ports_bind_to_loopback_by_default():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert '${WEB_BIND_HOST:-127.0.0.1}:${WEB_PORT:-15173}:5173' in compose
    assert '${MAIL_BIND_HOST:-127.0.0.1}:${MAIL_PORT:-13001}:3001' in compose
    assert '${BACKEND_BIND_HOST:-127.0.0.1}:${BACKEND_PORT:-18001}:8000' in compose
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python -m pytest server/backend/test_security_baseline.py -q`

Expected: both tests fail because the key is tracked/not ignored and ports have no bind host.

- [ ] **Step 3: Apply the minimal configuration changes**

Add `/server/backend/data/` to `.gitignore`.

Change the three Compose port mappings to:

```yaml
- "${WEB_BIND_HOST:-127.0.0.1}:${WEB_PORT:-15173}:5173"
- "${MAIL_BIND_HOST:-127.0.0.1}:${MAIL_PORT:-13001}:3001"
- "${BACKEND_BIND_HOST:-127.0.0.1}:${BACKEND_PORT:-18001}:8000"
```

Run `git rm --cached -- server/backend/data/secret.key`. This must preserve the local key file and only remove it from the Git index.

- [ ] **Step 4: Run the tests and verify GREEN**

Run: `python -m pytest server/backend/test_security_baseline.py -q`

Expected: 2 passed.

- [ ] **Step 5: Verify the local key still exists without reading it**

Run: `Test-Path server/backend/data/secret.key`

Expected: `True`.

### Task 2: Sanitize non-JSON MTOP failures

**Files:**
- Modify: `server/backend/test_mtop_client.py`
- Modify: `server/backend/app/services/xianyu/mtop_client.py`

- [ ] **Step 1: Write the failing regression test**

Add a test that returns a non-JSON response containing sentinel values resembling a Cookie and token, then asserts the raised `MtopError` string contains only the fixed Chinese parse-failure description and contains neither sentinel.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m pytest server/backend/test_mtop_client.py -q`

Expected: the new test fails because `resp.text[:200]` is included in the exception.

- [ ] **Step 3: Implement fixed parse-failure text**

Replace the raw response excerpt with a fixed message:

```python
raise MtopError("PARSE_ERROR", "闲鱼接口响应格式异常，未记录原始响应")
```

- [ ] **Step 4: Run focused and backend regression tests**

Run: `python -m pytest server/backend/test_mtop_client.py server/backend/test_order_service.py server/backend/test_security_baseline.py -q`

Expected: all tests pass.

### Task 3: Verify P0 as an integrated security baseline

**Files:**
- Verify only

- [ ] **Step 1: Run backend tests**

Run: `python -m pytest server/backend/test_selfcheck.py server/backend/test_mtop_client.py server/backend/test_order_service.py server/backend/test_security_baseline.py -q`

Expected: all collected tests pass.

- [ ] **Step 2: Run frontend tests and build**

Run: `npm test -- --run`

Expected: 80 tests pass.

Run: `npm run build`

Expected: TypeScript and Vite build exit successfully.

- [ ] **Step 3: Inspect the scoped diff**

Run: `git diff --check -- .gitignore docker-compose.yml server/backend/app/services/xianyu/mtop_client.py server/backend/test_mtop_client.py server/backend/test_security_baseline.py`

Expected: no whitespace errors.

- [ ] **Step 4: Confirm secrets remain absent from staged content**

Run: `git diff --cached --name-only`

Expected: `server/backend/data/secret.key` appears only as a deletion from version control; its contents must never be printed.

