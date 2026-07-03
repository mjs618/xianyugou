"""系统设置模型（单例，id=1）。smtp_pass 加密存储。"""
from typing import Optional
from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from .base import TimestampMixin


class Settings(TimestampMixin, Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # 固定为 1
    warranty_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    rebate_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)
    rebate_base: Mapped[str] = mapped_column(String(10), nullable=False, default="profit")  # profit/sale
    vip_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=500.0)
    core_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=2000.0)
    vip_trade_count: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    core_trade_count: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    recall_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    backup_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # SMTP 配置
    smtp_host: Mapped[str] = mapped_column(String(255), nullable=False, default="smtp.qq.com")
    smtp_port: Mapped[int] = mapped_column(Integer, nullable=False, default=465)
    smtp_user: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    smtp_pass: Mapped[str] = mapped_column(String(512), nullable=False, default="")  # 加密存储
    smtp_from: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
