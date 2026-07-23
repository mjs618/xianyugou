"""系统管理相关 schema：服务器备份列表、恢复请求与恢复报告。

E6 新增：从后端文件级 SQLite 备份（data/backups/daily/*.db）恢复数据库。
与前端 JSON 导入恢复（应用层数据）互补，这是文件级灾难恢复。
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BackupInfo(BaseModel):
    """一个可用备份文件的元信息。"""

    filename: str = Field(..., description="备份文件名，如 xianyu-20260714-120000.db")
    size_bytes: int = Field(..., description="备份文件大小（字节）")
    created_at: str = Field(..., description="备份创建时间（UTC ISO 格式）")
    table_counts: dict[str, int] = Field(
        default_factory=dict,
        description="备份内各表行数（从 manifest 读取，无 manifest 则为空）",
    )
    integrity_ok: bool = Field(..., description="manifest 中记录的 integrity_check 是否为 ok")


class BackupListResponse(BaseModel):
    """GET /api/system/backups 响应：可用备份列表。"""

    backups: list[BackupInfo] = Field(default_factory=list)
    backup_dir: str = Field(..., description="备份目录绝对路径（用于排查）")


class RestoreRequest(BaseModel):
    """POST /api/system/restore 请求体。

    confirm 必须为 True 才执行恢复（二次确认，防止误触发不可逆操作）。
    """

    filename: str = Field(..., description="要恢复的备份文件名（不含路径，从备份目录选）")
    confirm: bool = Field(
        False,
        description="二次确认标记，必须为 True 才执行恢复",
    )


class RestoreResponse(BaseModel):
    """POST /api/system/restore 响应：恢复结果报告。"""

    success: bool
    message: str
    pre_restore_path: str | None = Field(
        None, description="恢复前自动备份的旧数据库路径（回退用）"
    )
    integrity_check: str | None = None
    table_counts: dict[str, int] | None = None
