# Xianyu accounting system - Python backend service
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first to keep Docker layer caching effective.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code.
COPY app ./app

# Persist database and encryption key under /app/data.
RUN mkdir -p /app/data
VOLUME /app/data

EXPOSE 8000

ENV DATABASE_URL="sqlite+aiosqlite:////app/data/xianyu.db"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
