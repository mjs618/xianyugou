# 闲鱼记账系统 - Python 后端服务
FROM python:3.11-slim

WORKDIR /app

# 系统依赖（cryptography 等可能需要的构建/运行库）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 先装依赖（利用层缓存）
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app ./app

# 数据持久化目录
RUN mkdir -p /app/data
VOLUME /app/data

EXPOSE 8000

# 数据库文件与密钥都放在 /app/data（已挂载为卷）
ENV DATABASE_URL="sqlite+aiosqlite:////app/data/xianyu.db"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
