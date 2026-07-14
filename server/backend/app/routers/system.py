"""系统管理路由：服务器备份列表与数据库恢复。

E6 新增：从后端文件级 SQLite 备份（data/backups/daily/*.db）恢复数据库。
- GET  /api/system/backups：列出可用备份（文件名/大小/时间/表行数）
- POST /api/system/restore：触发恢复（需 confirm=True 二次确认）

恢复是不可逆操作：会覆盖当前数据库。限流 3 次/分钟，防止误触发。
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from ..config import settings as app_settings
from ..maintenance.backup_scheduler import BACKUP_DIR
from ..maintenance.database_backup import (
    BackupError,
    resolve_sqlite_path,
    restore_backup,
)
from ..schemas.system import (
    BackupInfo,
    BackupListResponse,
    RestoreRequest,
    RestoreResponse,
)
from ..security import limiter

router = APIRouter(prefix="/api/system", tags=["system"])

# 文件名安全校验：只允许字母/数字/下划线/连字符/点（防路径穿越）
import re

_SAFE_FILENAME_RE = re.compile(r"^[a-zA-Z0-9_.\-]+$")


@router.get("/backups", response_model=BackupListResponse)
async def list_backups():
    """列出可用的服务器备份文件。

    扫描备份目录下的 .db 文件，读取对应 manifest 获取表行数与完整性。
    无 manifest 的备份文件仍列出，但 integrity_ok=False 且 table_counts 为空。
    """
    backups: list[BackupInfo] = []
    if not BACKUP_DIR.exists():
        return BackupListResponse(backups=[], backup_dir=str(BACKUP_DIR))

    for db_file in sorted(BACKUP_DIR.iterdir(), key=lambda f: f.name, reverse=True):
        if not db_file.is_file() or db_file.suffix != ".db":
            continue
        # manifest 路径与 create_backup 一致：backup.db → backup.manifest.json
        manifest_path = db_file.with_suffix(".manifest.json")
        table_counts: dict[str, int] = {}
        integrity_ok = False
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                table_counts = {
                    str(k): int(v)
                    for k, v in manifest.get("table_counts", {}).items()
                }
                integrity_ok = manifest.get("integrity_check") == "ok"
            except (json.JSONDecodeError, ValueError, TypeError):
                # manifest 损坏：仍列出文件，但标记为不可信
                pass
        stat = db_file.stat()
        backups.append(
            BackupInfo(
                filename=db_file.name,
                size_bytes=stat.st_size,
                created_at=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                table_counts=table_counts,
                integrity_ok=integrity_ok,
            )
        )

    return BackupListResponse(backups=backups, backup_dir=str(BACKUP_DIR))


@router.post("/restore", response_model=RestoreResponse)
@limiter.limit("3/minute")
async def restore(request: Request, payload: RestoreRequest):
    """从服务器备份文件恢复数据库（不可逆，覆盖当前数据）。

    二次确认：``payload.confirm`` 必须为 True 才执行恢复。
    文件名安全校验：只允许字母/数字/下划线/连字符/点，防路径穿越。

    恢复流程：
    1. 校验备份（manifest sha256 + 表数 + integrity）
    2. 备份当前 db 到 .pre_restore.bak（回退用）
    3. SQLite backup API 在线复制 backup → target
    4. 返回恢复报告

    恢复后建议前端 reload 页面（刷新所有 ORM 缓存）。
    """
    if not payload.confirm:
        raise HTTPException(400, "必须传 confirm=true 才能执行恢复（二次确认）")
    if not _SAFE_FILENAME_RE.match(payload.filename):
        raise HTTPException(400, "文件名包含非法字符")

    backup_path = BACKUP_DIR / payload.filename
    if not backup_path.is_file():
        raise HTTPException(404, f"备份文件不存在：{payload.filename}")

    # 解析活跃数据库路径
    try:
        target_path = resolve_sqlite_path(app_settings.database_url)
    except BackupError as exc:
        raise HTTPException(500, f"无法解析数据库路径：{exc}")

    # restore_backup 是同步阻塞操作（SQLite 文件 IO），放到线程池
    try:
        report = await asyncio.to_thread(restore_backup, backup_path, target_path)
    except BackupError as exc:
        return RestoreResponse(success=False, message=f"恢复失败：{exc}")
    except Exception as exc:
        return RestoreResponse(success=False, message=f"恢复异常：{exc}")

    return RestoreResponse(
        success=True,
        message="数据库已恢复，建议刷新页面以加载最新数据",
        pre_restore_path=report.get("pre_restore_path"),
        integrity_check=report.get("integrity_check"),
        table_counts=report.get("table_counts"),
    )
