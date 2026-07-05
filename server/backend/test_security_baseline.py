import subprocess
from pathlib import Path

import pytest

from app.config import Settings
from app.utils import crypto


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_SECRET = "server/backend/data/secret.key"


def test_runtime_secret_is_ignored_and_untracked():
    gitignore_entries = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
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

    assert "/server/backend/data/" in gitignore_entries
    assert ignored.returncode == 0
    assert tracked.returncode != 0


def test_missing_key_with_existing_default_database_fails_closed(tmp_path, monkeypatch):
    key_path = tmp_path / "data" / "secret.key"
    database_path = tmp_path / "data" / "xianyu.db"
    database_path.parent.mkdir(parents=True)
    database_path.touch()
    monkeypatch.setattr(crypto, "_SECRET_KEY_PATH", key_path)
    monkeypatch.setattr(crypto, "DEFAULT_DB_PATH", database_path, raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        crypto._load_or_create_key()

    assert str(exc_info.value) == (
        "Encryption key is missing while the existing database is present; "
        "restore the matching key before starting."
    )
    assert not key_path.exists()


def test_missing_key_without_default_database_allows_first_initialization(
    tmp_path, monkeypatch
):
    key_path = tmp_path / "data" / "secret.key"
    database_path = tmp_path / "data" / "xianyu.db"
    monkeypatch.setattr(crypto, "_SECRET_KEY_PATH", key_path)
    monkeypatch.setattr(crypto, "DEFAULT_DB_PATH", database_path, raising=False)

    key = crypto._load_or_create_key()

    assert len(key) == 32
    assert key_path.exists()


def test_startup_initializes_encryption_key_before_default_database():
    main_source = (REPO_ROOT / "server/backend/app/main.py").read_text(encoding="utf-8")

    assert "from .utils.crypto import _load_or_create_key" in main_source
    assert main_source.index("_load_or_create_key()") < main_source.index("await init_db()")


def test_compose_ports_bind_to_loopback_by_default():
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "${WEB_BIND_HOST:-127.0.0.1}:${WEB_PORT:-15173}:5173" in compose
    assert "${MAIL_BIND_HOST:-127.0.0.1}:${MAIL_PORT:-13001}:3001" in compose
    assert "${BACKEND_BIND_HOST:-127.0.0.1}:${BACKEND_PORT:-18001}:8000" in compose


def test_frontend_build_consumes_configured_local_service_urls():
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    api_client = (REPO_ROOT / "src/services/apiClient.ts").read_text(encoding="utf-8")
    mail_service = (REPO_ROOT / "src/services/mailService.ts").read_text(encoding="utf-8")

    assert "NODE_VERSION: ${NODE_VERSION:-20-alpine}" in compose
    assert (
        "VITE_BACKEND_URL: "
        "${VITE_BACKEND_URL:-http://localhost:${BACKEND_PORT:-18001}}"
    ) in compose
    assert (
        "VITE_MAIL_SERVER_URL: "
        "${VITE_MAIL_SERVER_URL:-http://localhost:${MAIL_PORT:-13001}}"
    ) in compose
    assert "ARG NODE_VERSION=" in dockerfile
    assert "FROM node:${NODE_VERSION}" in dockerfile
    assert "ARG VITE_BACKEND_URL=" in dockerfile
    assert "ENV VITE_BACKEND_URL=${VITE_BACKEND_URL}" in dockerfile
    assert "ARG VITE_MAIL_SERVER_URL=" in dockerfile
    assert "ENV VITE_MAIL_SERVER_URL=${VITE_MAIL_SERVER_URL}" in dockerfile
    assert "'http://localhost:18001'" in api_client
    assert "'http://localhost:13001'" in mail_service


def test_local_content_security_policy_allows_configurable_ports():
    index = (REPO_ROOT / "index.html").read_text(encoding="utf-8")

    assert "http://localhost:*" in index
    assert "http://127.0.0.1:*" in index
    assert "ws://localhost:*" in index
    assert "ws://127.0.0.1:*" in index


def test_backend_reads_cors_origins_from_environment(monkeypatch):
    origins = "http://localhost:15173,http://127.0.0.1:15173"
    monkeypatch.setenv("CORS_ORIGINS", origins)

    configured = Settings(_env_file=None)
    main_source = (REPO_ROOT / "server/backend/app/main.py").read_text(encoding="utf-8")

    assert configured.cors_origin_list == origins.split(",")
    assert "allow_origins=settings.cors_origin_list" in main_source
