# 阶段 3B：后端 Schema 领域边界设计

## 目标

将 400 行的单文件 `app/schemas.py` 拆成按领域组织的 `app/schemas/` 包，同时保持所有现有导入、Pydantic 字段、默认值、校验约束、OpenAPI schema 名称和 API 行为不变。

## 当前状态

- `schemas.py` 定义 40 个 Pydantic 模型（含共享基类），覆盖客户、交易、售后、返利、运营支出、商品模板、系统设置、审计、迁移、附件、闲鱼同步和通用响应。
- 所有调用方都从公共入口 `app.schemas` 导入具体类型，没有调用方依赖定义文件内部实现。
- 模型之间只有一个共享基类 `ORMBase`，没有跨领域前向引用或复杂继承。
- 阶段 3A 已完成路由领域拆分，Schema 单文件现在是最明显的剩余边界聚合点。

## 方案比较

### 方案 A：Schema package + 兼容导出门面

每个领域文件定义自己的模型，`schemas/__init__.py` 显式重新导出全部公共名称。外部导入完全不变，内部归属清晰，迁移风险最低。采用。

### 方案 B：拆分文件并修改所有路由为领域直连导入

边界更显式，但会同时修改所有路由导入，扩大 diff，并让未来跨领域复用需要了解内部文件布局。本阶段不采用。

### 方案 C：保留 `schemas.py`，把部分模型放入旁路模块

可以渐进迁移，但会长期存在两个定义入口，容易重新堆积，且无法形成清晰完成状态。不采用。

## 包结构

建立以下结构：

- `schemas/base.py`：`ORMBase`。
- `schemas/customers.py`：`CustomerOut/Create/Update`。
- `schemas/transactions.py`：`TransactionOut/Create/Update`、`StatusChange`。
- `schemas/aftersales.py`：`AfterSalesOut/Create/Update`。
- `schemas/rebates.py`：`RebateOut/StatusChange/BatchPay`。
- `schemas/expenses.py`：`OperatingExpenseOut/Create/Update`。
- `schemas/product_templates.py`：`ProductTemplateOut/Create/Update`。
- `schemas/settings.py`：`SettingsOut/Update`。
- `schemas/audit.py`：`OperationLogOut`、`LogListResponse`。
- `schemas/migrate.py`：`MigrateImportResponse`。
- `schemas/attachments.py`：`AttachmentOut`、`AttachmentBatchRequest`。
- `schemas/xianyu.py`：闲鱼账号、CookieCloud、同步结果、商品镜像和订单镜像模型。
- `schemas/common.py`：`MessageResponse`、`HealthResponse`。
- `schemas/__init__.py`：显式导入并通过 `__all__` 发布原有 40 个公共名称（含 `ORMBase`）。

删除原 `schemas.py`，不保留双重定义源。

## 兼容性规则

- `from app.schemas import CustomerOut` 等所有现有导入继续工作。
- 类名、字段顺序、类型、Optional 语义、默认值、Field 约束和 `model_config` 原样保留。
- OpenAPI 中的 schema component 名称继续使用类名，不因 Python 模块路径变化而改变。
- 路由、服务、模型、数据库与前端均无需修改。
- `__init__.py` 必须使用显式导出，不采用 wildcard import 或自动扫描。

## 边界保护

新增 `test_schema_boundaries.py`：

1. 校验原有公共名称集合全部可从 `app.schemas` 获取，并与 `__all__` 完全一致。
2. 校验每个代表模型的 `__module__` 属于正确领域文件。
3. 校验公共模型仍可生成 JSON schema，关键 Field 约束仍存在。
4. 校验旧 `app/schemas.py` 不存在，领域目录文件集合完整。

现有路由测试与 FastAPI OpenAPI 生成提供第二层行为保护。

## 实施顺序

1. 先新增公共导出与模型归属测试；当前结构应因不存在领域包而失败。
2. 创建 `schemas/` 包和领域模块，逐段原样移动模型。
3. 创建显式兼容导出门面并删除原文件。
4. 运行 Schema 边界测试、路由契约测试、OpenAPI 生成和后端全量测试。
5. 重建后端容器，验证健康、设置、交易和闲鱼相关只读端点。

## 错误处理与回滚

- 任何遗漏导出会在应用导入或公共名称测试阶段立即失败。
- 任何字段漂移会由关键约束测试或现有路由测试暴露。
- 本阶段不改变数据库或数据，回滚只需回退 Schema 拆分提交。

## 非目标

- 不修改 Pydantic mutable default 的既有写法。
- 不重命名模型、字段或响应结构。
- 不修改路由导入路径到内部领域模块。
- 不生成新的通用 DTO 抽象或跨领域基类。
- 不拆分闲鱼服务、交易服务或数据库模型。

## 验收标准

- `schemas.py` 被领域包完全替代，所有公共名称兼容。
- Schema 边界、路由契约、OpenAPI 和后端全量测试通过。
- 前端测试、类型检查和构建通过。
- 后端容器重建后相关只读端点返回 200，Alembic 与备份校验保持正常。
