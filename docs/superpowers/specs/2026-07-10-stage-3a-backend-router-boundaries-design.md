# 阶段 3A：后端路由模块边界设计

## 目标

把当前 `routers/settings.py` 中混合的六个业务领域拆成独立路由模块，在不改变任何 URL、HTTP 方法、请求响应、事务行为或前端调用的前提下，建立可持续的后端路由边界。

## 当前状态

- 后端服务层不调用 `commit`，路由层统一提交事务，事务边界已经一致，本阶段不调整。
- `routers/settings.py` 共约 247 行，同时定义设置、商品模板、财务、运营支出、审计日志和备份迁移六组路由。
- `main.py` 通过 `settings_router_module` 间接取得六个 router，文件名与实际职责不符。
- 已批准的总体架构设计明确要求逐步把商品、财务、审计和迁移接口移出 `routers/settings.py`。

## 方案比较

### 方案 A：机械拆分为六个路由文件

每个文件只依赖本领域 schema 与 service，`main.py` 显式注册。改动可审查、API 契约不变、容易用路由表测试保护。采用。

### 方案 B：改造成完整 feature package

同时移动 router、schema、service、model 到领域包，长期边界最强，但会造成大规模 import 迁移并显著提高回归风险。留到确有必要时逐领域实施，本阶段不采用。

### 方案 C：保留文件，仅增加注释与约束测试

风险最低，但混合职责和间接注册仍然存在，不能真正改善维护边界。不采用。

## 模块设计

拆分后保持现有扁平路由目录风格：

- `routers/settings.py`：仅 `/api/settings`。
- `routers/product_templates.py`：仅 `/api/product-templates`。
- `routers/finance.py`：仅 `/api/finance`。
- `routers/expenses.py`：仅 `/api/expenses`。
- `routers/audit.py`：仅 `/api/operation-logs`。
- `routers/migrate.py`：仅 `/api/migrate`。

每个模块统一导出 `router`，与 customers、transactions、attachments 等现有模块保持一致。`main.py` 显式导入并逐个 `app.include_router(...)`，不引入自动扫描、注册表或装饰器魔法。

## API 与数据流

本阶段是结构重构，以下契约必须逐项保持：

- 所有路径、HTTP 方法和 response model 不变。
- Query 参数默认值和边界不变。
- 异常状态码与中文错误信息不变。
- 每个现有读写处理器继续在返回前执行相同次数的 `db.commit()`。
- `parse_date` 调用方式保持不变，不改变日期口径。

前端无需修改，数据库模型和 Alembic revision 不变。

## 边界保护

新增 `test_router_boundaries.py`：

1. 从 FastAPI `app.routes` 收集六个领域的 method/path 集合，与拆分前固定契约逐项比较。
2. 检查六个路由模块均导出名为 `router` 的 `APIRouter`。
3. 检查 `settings.py` 不再出现其他五个领域的 URL 前缀或 service 名称。
4. 检查 `main.py` 不再引用 `settings_router_module` 或多 router 属性。

现有 `test_settings_routes.py`、`test_product_template_routes.py` 和全量后端测试继续提供行为回归保护。

## 实施顺序

1. 先写路由契约与源码边界测试，确认当前结构因混合职责而失败。
2. 分别创建五个新路由文件，把对应代码原样移动。
3. 收缩 `settings.py`，统一所有模块导出 `router`。
4. 更新 `main.py` 显式注册。
5. 运行焦点测试、全量后端测试、前端 API 服务测试与 Docker 健康检查。

## 错误处理与回滚

- 不修改业务异常类型或 catch 范围，避免结构重构改变 HTTP 语义。
- 任一路由契约缺失或重复都会由固定 method/path 测试阻止提交。
- 本阶段不产生数据库变更，回滚只需回退路由拆分提交。

## 非目标

- 不拆分 `schemas.py`。
- 不拆分闲鱼账号、订单和商品镜像路由或服务。
- 不调整 service 之间的领域协作。
- 不引入 Unit of Work、依赖注入容器、自动路由发现或新的第三方库。
- 不修改任何前端代码或公开 API。

## 验收标准

- 六个领域各自只有一个明确路由模块，均导出 `router`。
- FastAPI 路由 method/path 集合与拆分前一致，无缺失、重复或新增。
- 后端全量测试通过，Alembic current=head，容器重建后健康检查为 200。
- `git diff --check` 通过，工作区最终干净。
