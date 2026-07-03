# 多阶段构建：前端静态服务 + 邮件服务

# ==================== 构建阶段 ====================
FROM node:18-alpine AS builder

WORKDIR /app

# 先复制依赖清单，利用 Docker 层缓存
COPY package*.json ./
RUN npm ci

# 复制源码并构建前端产物
COPY . .
RUN npm run build

# ==================== 前端静态服务 ====================
FROM node:18-alpine AS web

WORKDIR /app

COPY package*.json ./
RUN npm ci --omit=dev

COPY --from=builder /app/dist ./dist
COPY serve-dist.cjs ./

EXPOSE 5173

CMD ["node", "serve-dist.cjs"]

# ==================== 邮件发送服务 ====================
FROM node:18-alpine AS mail

WORKDIR /app

COPY package*.json ./
RUN npm ci --omit=dev

COPY server/mail-server.mjs ./server/

EXPOSE 3001

ENV MAIL_PORT=3001

CMD ["node", "server/mail-server.mjs"]
