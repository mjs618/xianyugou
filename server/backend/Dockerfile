# Xianyu accounting system - Python backend service
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first to keep Docker layer caching effective.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code.
COPY app ./app
COPY entrypoint.sh ./

# Persist database and encryption key under /app/data.
RUN mkdir -p /app/data
VOLUME /app/data

EXPOSE 8000

ENV DATABASE_URL="sqlite+aiosqlite:////app/data/xianyu.db"

# 入口脚本先执行数据库迁移，再启动 uvicorn
RUN chmod +x entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]
