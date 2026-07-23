from typing import Optional

from pydantic import BaseModel

from .base import ORMBase


class SettingsOut(ORMBase):
    id: int
    warranty_days: int
    rebate_rate: float
    rebate_base: str
    vip_threshold: float
    core_threshold: float
    vip_trade_count: int
    core_trade_count: int
    recall_days: int
    backup_path: Optional[str] = None
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str
    smtp_from: Optional[str] = None


class SettingsUpdate(BaseModel):
    warranty_days: Optional[int] = None
    rebate_rate: Optional[float] = None
    rebate_base: Optional[str] = None
    vip_threshold: Optional[float] = None
    core_threshold: Optional[float] = None
    vip_trade_count: Optional[int] = None
    core_trade_count: Optional[int] = None
    recall_days: Optional[int] = None
    backup_path: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_pass: Optional[str] = None
    smtp_from: Optional[str] = None
