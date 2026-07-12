#!/bin/sh
set -e

# 容器入口：先执行数据库迁移，再启动应用。
# migrate_database 自动检测数据库状态：
#   - 全新数据库：upgrade 从头创建 schema
#   - 旧版无版本数据库：adopt 后 upgrade
#   - 已有版本但非 head：upgrade 到 head
#   - 已在 head：无操作
echo ">>> 正在检查/迁移数据库 schema..."
python -m app.maintenance.database_schema migrate

echo ">>> 启动 FastAPI 应用..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
