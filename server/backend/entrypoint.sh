#!/bin/sh
set -e

# 容器默认以 root 启动（Dockerfile 未设 USER）。
# 先修复数据卷权限（Docker named volume 首次挂载属主是 root），
# 再用 gosu 切换到非 root 用户执行迁移和启动 uvicorn，确保运行进程 uid=1000。
if [ "$(id -u)" = "0" ]; then
    chown -R 1000:1000 /app/data
    echo ">>> 正在检查/迁移数据库 schema..."
    gosu appuser python -m app.maintenance.database_schema migrate
    echo ">>> 启动 FastAPI 应用（user=appuser）..."
    exec gosu appuser "$@"
else
    # 已是非 root 用户（如 docker exec --user appuser），直接执行
    echo ">>> 正在检查/迁移数据库 schema..."
    python -m app.maintenance.database_schema migrate
    echo ">>> 启动 FastAPI 应用..."
    exec "$@"
fi
