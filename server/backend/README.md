# 闲鱼记账系统 - Python 后端

为闲鱼记账与客户管理系统（前端 React 应用）提供后端能力：**闲鱼订单自动同步**、数据统一管理、跨设备共享。

技术栈：FastAPI + SQLAlchemy 2.0（异步）+ SQLite（可切 MySQL）。

## 与前端的关系

- 前端原本是纯本地应用（数据在浏览器 IndexedDB），本后端是**增量增强**，不破坏现有功能。
- 通过「设置 → 迁移到后端」一键把本地数据迁移到后端，之后可用「订单同步」自动拉取闲鱼订单。
- 也可随时「从后端恢复」把数据拉回本地，双向同步。

## 目录结构

```
server/backend/
├── app/
│   ├── main.py              # FastAPI 入口（路由注册、CORS、生命周期建表）
│   ├── config.py            # 配置（数据库、端口、加密密钥）
│   ├── database.py          # SQLAlchemy 异步引擎 + 会话
│   ├── schemas.py           # Pydantic 请求/响应模型
│   ├── models/              # 17 张 ORM 表（15 业务表 + 2 闲鱼表）
│   ├── routers/             # API 路由（按模块拆分）
│   ├── services/            # 业务逻辑（复刻前端 TS service 的级联）
│   │   └── xianyu/          # 闲鱼对接（Cookie/MTOP/订单同步）
│   └── utils/               # 加密、日期工具
├── requirements.txt
├── Dockerfile
└── test_selfcheck.py        # 自测脚本（26 项，验证核心闭环）
```

## 快速开始

### 1. 安装依赖

```bash
cd server/backend
python -m pip install -r requirements.txt
```

> 若网络环境使用代理且代理未运行，pip 可能报 `ProxyError`/`SSLError`。
> 临时解决：`NO_PROXY="*" python -m pip install -r requirements.txt`

### 2. 启动服务

```bash
# 方式一：直接 uvicorn（开发热重载）
cd server/backend
uvicorn app.main:app --reload --port 8000

# 方式二：通过前端项目根目录的 npm 脚本
cd ../..
npm run backend
```

启动后：
- API 文档（Swagger）：http://localhost:8000/docs
- 健康检查：http://localhost:8000/api/health

### 3. 自测

```bash
# 先启动后端，再跑：
cd server/backend
python test_selfcheck.py
```

预期输出 `26 通过, 0 失败`，覆盖：客户/交易级联、推荐返利、售后状态联动、迁移往返、敏感字段加密等。

## 配置

通过环境变量或 `server/backend/.env` 文件配置；使用 Docker Compose 时，可复制项目根目录 `.env.example` 为 `.env` 后填写。

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///.../data/xianyu.db` | 数据库连接串。切 MySQL：`mysql+asyncmy://user:pass@host:3306/xianyu_data` |
| `PORT` | `8000` | 服务端口 |
| `SECRET_KEY` | （首次启动随机生成） | AES-GCM 加密主密钥，**切勿随意更换**，否则已加密数据无法解密 |
| `COOKIE_CLOUD_HOST` | 空 | 可选。自建 CookieCloud 服务地址，如 `http://127.0.0.1:8088` |
| `COOKIE_CLOUD_UUID` | 空 | 可选。CookieCloud 浏览器插件生成的 UUID |
| `COOKIE_CLOUD_PASSWORD` | 空 | 可选。CookieCloud 浏览器插件生成的加密密码 |
| `COOKIE_CLOUD_DOMAIN_KEYWORD` | `goofish.com` | 可选。只提取匹配该关键词的 Cookie，避免混入其他站点 Cookie |

## 数据安全

- 敏感字段（SMTP 授权码、GPT 密码、邮箱密码、闲鱼 Cookie）使用 **AES-256-GCM** 加密存储。
- 主密钥持久化在 `data/secret.key`，首次启动自动生成。
- 加密值带 `enc:v1:` 前缀，便于识别。
- 备份导出时解密为明文（与前端 `exportJSON` 口径一致），导入后自动重新加密。

## 闲鱼订单同步

### 工作流程

1. 在浏览器登录闲鱼（goofish.com）
2. 打开开发者工具 → Network → 复制任意请求的完整 Cookie
3. 前端「订单同步」页 → 添加账号 → 粘贴 Cookie（后端校验 `unb` / `_m_h5_tk` 字段）
4. 点击「同步订单」→ 后端调用 MTOP API 拉取成交订单 → 自动写入交易表（含客户建立、利润计算、质保生成、按订单号去重）

### CookieCloud 自动刷新（可选）

如果配置了 `COOKIE_CLOUD_HOST`、`COOKIE_CLOUD_UUID`、`COOKIE_CLOUD_PASSWORD`，订单同步或商品同步遇到 `AUTH_FAIL` / Session 过期时，会尝试从 CookieCloud 拉取最新 `goofish.com` Cookie，校验通过后加密保存到账号，再自动重试一次。

建议使用自建 CookieCloud，并在本机 Chrome 登录闲鱼 Web 后通过 CookieCloud 插件同步 `goofish.com` Cookie。若闲鱼触发验证码、滑块或风控，系统仍会停止请求并提示人工处理，不会绕过平台风控。

可通过 `/api/xianyu/cookiecloud/status` 查看本地配置状态。该接口只返回是否启用、缺失的环境变量名和下一步提示，不返回 UUID、密码或 Cookie 内容。

### 关键 API

| 接口 | 方法 | 说明 |
|---|---|---|
| `/api/xianyu/accounts` | GET/POST | 账号列表 / 添加 |
| `/api/xianyu/accounts/{id}/test` | POST | 校验 Cookie |
| `/api/xianyu/cookiecloud/status` | GET | 查看 CookieCloud 自动续 Cookie 配置状态 |
| `/api/xianyu/accounts/{id}/sync-orders` | POST | 触发订单同步 |
| `/api/xianyu/accounts/{id}/sync-logs` | GET | 同步日志 |
| `/api/migrate/import` | POST | 导入备份（前端 exportJSON 格式） |
| `/api/migrate/export` | GET | 导出备份 |

## ⚠️ 风险提示

闲鱼订单同步依赖**逆向私有协议**（MTOP H5 API + MD5 签名）。这些协议可能随闲鱼更新而失效，需要持续维护。本后端**只实现了订单拉取所需的最小能力**，未移植参考项目的反爬/风控/滑块验证逻辑。若触发风控（验证码），需重新登录获取新 Cookie。

## 技术约束

- 兼容 Python 3.9+（部分文件使用 `from __future__ import annotations` 以支持联合类型注解）
- `greenlet` 锁定 3.0.3（提供 Python 3.9 预编译 wheel，避免源码编译）

## 数据库备份与校验

结构迁移或镜像升级前，在项目根目录执行以下命令，直接备份 Docker volume 中的运行数据库：

```powershell
docker compose exec backend python -m app.maintenance.database_backup create --output /app/backups/xianyu-YYYYMMDD-HHMMSS.db
```

Compose 自动加载 `docker-compose.override.yml`，将 `/app/backups` 映射到宿主机 `server/backend/backups`。该命令使用 SQLite 在线备份 API，不覆盖已有文件，并生成同名 `.manifest.json`。清单只包含校验和、表名和记录数，不包含业务字段值或密钥。

恢复前先校验备份：

```powershell
docker compose exec backend python -m app.maintenance.database_backup verify --database /app/backups/xianyu-YYYYMMDD-HHMMSS.db --manifest /app/backups/xianyu-YYYYMMDD-HHMMSS.manifest.json
```

数据库与 `data/secret.key` 必须配套保存。工具不会复制或打印密钥。实际恢复涉及覆盖运行数据库，必须先停止后端并由操作者明确执行；本工具只负责创建和校验备份。

## 数据库版本迁移

数据库结构由 `app/migrations` 下的 Alembic 版本管理。应用启动只检查数据库是否位于 packaged head，不会自动建表或升级；版本缺失、落后或超前时，后端拒绝启动。

现有未纳入 Alembic 的数据库只能在备份验证通过后接管一次：

```powershell
docker compose run --rm backend python -m app.maintenance.database_schema adopt
```

`adopt` 会先校验所有必需表和列；发现结构缺失时会在写入版本号前停止。校验通过后，数据库先标记到基线版本，再执行兼容迁移。

新数据库或后续版本升级使用：

```powershell
docker compose run --rm backend python -m app.maintenance.database_schema upgrade
```

只读查看当前版本与 packaged head：

```powershell
docker compose exec backend python -m app.maintenance.database_schema current
```

结构升级前必须按上一节创建并验证数据库备份。迁移失败时不要继续启动新容器，应恢复匹配的数据库与 `data/secret.key`，再回退到上一个后端镜像。
