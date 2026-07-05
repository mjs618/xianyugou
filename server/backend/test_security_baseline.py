import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_SECRET = "server/backend/data/secret.key"


def test_runtime_secret_is_ignored_and_untracked():
    ignored = subprocess.run(
        ["git", "check-ignore", RUNTIME_SECRET],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", RUNTIME_SECRET],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert ignored.returncode == 0
    assert tracked.returncode != 0


def test_compose_ports_bind_to_loopback_by_default():
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "${WEB_BIND_HOST:-127.0.0.1}:${WEB_PORT:-15173}:5173" in compose
    assert "${MAIL_BIND_HOST:-127.0.0.1}:${MAIL_PORT:-13001}:3001" in compose
    assert "${BACKEND_BIND_HOST:-127.0.0.1}:${BACKEND_PORT:-18001}:8000" in compose
