# 阶段 3D：闲鱼商品解析边界设计

## 目标

从 368 行的 `app/services/xianyu/item_service.py` 中抽离纯商品载荷解析职责，建立仅依赖标准库的 `item_parser.py`，同时保持商品拉取、镜像写入、模板导入、鉴权重试、API 与 OpenAPI 契约不变。

## 当前状态

- `item_service.py` 同时承担原始卡片解包、字段兼容、价格解析、用户 ID 解析、MTOP 分页、账号状态、商品镜像和模板投影。
- 前 150 行左右的解析逻辑没有数据库或网络副作用，适合形成独立边界。
- 阶段 3C 已用同一模式拆出订单解析器，形成了可复用但不需要抽象基类的项目内范式。
- 仓库内没有调用方直接依赖商品服务的私有解析函数。

## 方案比较

### 方案 A：只抽离纯商品载荷解析器

移动卡片解包、通用取值、价格转换、商品字段、列表响应和用户 ID 解析。分页与所有副作用留在服务。依赖单向、行为面最小。采用。

### 方案 B：同时抽离分页状态解析

把 `nextPageModel`、`nextPageNum` 和是否继续翻页也封装为解析结果。能进一步缩短服务，但会引入新数据结构并改变拉取循环，不符合本阶段 YAGNI 原则。不采用。

### 方案 C：同时拆分模板投影

把商品镜像导入模板的 ORM 查询与写入移到新模块。会触及数据库事务和跨实体规则，验证面过大。不采用。

## 模块结构

新增 `app/services/xianyu/item_parser.py`，公开：

- `extract_item_id`、`extract_title`、`extract_price`、`extract_status`、`extract_image_url`。
- `parse_items`：兼容 `module.items/list/itemList/cardList`、顶层列表字段、`result` 和 `data` 路径，只返回字典项。
- `extract_user_id`：兼容账号响应中的现有用户 ID 路径。

`nested`、`coerce_price`、`first_text` 和 `unwrap_item` 保持模块私有，作为公开解析函数的实现细节。

`item_service.py` 保留：

- MTOP 用户 ID 请求和商品分页拉取。
- CookieCloud 鉴权重试与账号状态维护。
- 商品镜像查询和写入。
- 商品镜像到模板的幂等投影。

## 依赖与兼容规则

- `item_parser.py` 仅导入 `typing`，不得导入 SQLAlchemy、FastAPI、应用模型、MTOP 客户端、加密或数据库工具。
- 服务通过显式导入使用解析器；解析器不得反向依赖服务。
- 继续接收并返回原始 `dict` / `list[dict]`，不引入 DTO、dataclass 或通用解析框架。
- `fetch_items`、`upsert_item_mirror`、`list_item_mirrors`、`sync_items_for_account` 和 `import_item_mirrors_as_templates` 的路径与签名不变。
- 原私有解析函数不保留兼容别名；经全仓库搜索确认无调用方依赖。

## 行为兼容

- 嵌套卡片仍按 `cardData`、`item`、`itemDO`、`itemVO`、`itemInfo`、`data`、`detailParams` 的原优先级展开。
- 字段优先级、空文本处理、人民币符号和千分位清理保持不变。
- 整数价格大于 1000 时继续按分换算，无法解析时商品价格仍回退为 `0.0`。
- 商品列表响应路径、非字典项过滤和空响应行为保持不变。
- 用户 ID 路径优先级保持不变；账号接口失败仍由服务返回 `None`。
- 分页大小、令牌传递、最大页数和鉴权重试控制流不变。

## 测试策略

新增 `test_xianyu_item_parser.py`：

1. 先动态检查新模块，在模块缺失时以断言失败建立 RED 基线。
2. 覆盖顶层和卡片嵌套字段、价格格式、图片与状态。
3. 覆盖列表响应路径、非字典项过滤和用户 ID 路径。
4. 断言公开函数归属新模块，并用 AST 限制依赖仅为标准库 `typing`。
5. 源码边界断言 `item_service.py` 不再定义重复解析函数。

现有商品服务、商品路由和订单模板联动测试继续保护数据库与同步行为。

## 实施顺序

1. 新增解析器契约测试，确认因模块缺失而失败。
2. 创建 `item_parser.py`，原样迁移纯解析逻辑并公开命名。
3. 修改 `item_service.py` 为显式导入，删除重复实现。
4. 运行解析器、商品服务与路由测试，再执行前后端全量回归。
5. 重建后端容器，验证健康、账号、商品列表和 OpenAPI，复验 Alembic 与备份。

## 回滚

本阶段无数据库、迁移、路由或前端修改。回退实现提交即可恢复单文件服务，不需要数据回滚。

## 非目标

- 不抽象订单与商品解析器的共享基类。
- 不修改商品分页、账号鉴权或 Cookie 刷新流程。
- 不拆分商品镜像或模板投影。
- 不改变字段兼容与价格规则。
- 不处理现有 datetime、Vite 或依赖告警。

## 验收标准

- 商品纯解析逻辑归属 `item_parser.py`，且只依赖标准库。
- `item_service.py` 不再定义重复解析函数，公开入口保持兼容。
- 新解析器测试、现有商品同步/路由测试和后端全量测试通过。
- 前端测试、类型检查和生产构建通过。
- 后端容器关键只读端点返回 200，Alembic 与备份校验正常。
