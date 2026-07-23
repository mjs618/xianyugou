# Xianyu accounting system - Python backend service
FROM python:3.11-slim

WORKDIR /app

# gosu: entrypoint 以 root 启动后切换到非 root 用户执行 uvicorn
RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first to keep Docker layer caching effective.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code.
COPY app ./app
COPY entrypoint.sh ./

# 创建非 root 用户（uid=1000，与 docker-compose user 字段对齐）
RUN useradd --system --uid 1000 --home /app --shell /sbin/nologin appuser \
    && chown -R appuser:appuser /app

# Persist database and encryption key under /app/data.
RUN mkdir -p /app/data
VOLUME /app/data

EXPOSE 8000

ENV DATABASE_URL="sqlite+aiosqlite:////app/data/xianyu.db"

# 入口脚本先修复数据卷权限，再执行数据库迁移，最后以非 root 用户启动 uvicorn
RUN chmod +x entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]
# P2-6 修复：uvicorn 优雅关停
# --timeout-graceful-shutdown=30：收到 SIGTERM 后等待在途请求完成（最多 30 秒）
#   让同步任务 / 备份任务有足够时间安全收尾，避免事务半提交
# --timeout-keep-alive=5：keep-alive 连接保活时间缩短，便于快速关停
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--timeout-graceful-shutdown", "30", "--timeout-keep-alive", "5"]
