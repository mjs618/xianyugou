"""应用配置 - 通过环境变量 / .env 配置"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


# 后端根目录：server/backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent
# 数据库文件默认放在 server/backend/data/xianyu.db
DEFAULT_DB_PATH = BACKEND_DIR / "data" / "xianyu.db"


class Settings(BaseSettings):
    """全局配置。优先读环境变量，其次 .env 文件，最后用默认值。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 服务
    app_name: str = "闲鱼记账与客户管理系统 API"
    host: str = "0.0.0.0"
    port: int = 8000

    # 数据库。默认 SQLite 单文件；若要切 MySQL，改为
    # mysql+asyncmy://user:pass@host:3306/xianyu_data
    database_url: str = f"sqlite+aiosqlite:///{DEFAULT_DB_PATH}"

    # 敏感字段加密主密钥（AES-GCM 256）。
    # 首次启动若为空，会随机生成并持久化到 data/secret.key。
    # 切勿随意更换，否则已加密数据无法解密。
    secret_key: str = ""

    # 闲鱼对接（第二阶段使用）
    xianyu_app_key: str = "34839810"
    xianyu_mtop_endpoint: str = "https://h5api.m.goofish.com/h5/{api}/{version}/"
    xianyu_origin: str = "https://www.goofish.com"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


settings = Settings()
