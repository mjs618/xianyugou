# 阶段 3E：财务纯计算边界设计

## 目标

将 `finance_service.py` 中不依赖数据库的财务聚合逻辑抽离为 `finance_calculations.py`，使服务层只负责时间窗口和 SQL 查询，同时保持所有财务 API、统计口径、字段名和数据库行为不变。

## 当前状态

- `finance_service.py` 为 312 行，混合 SQL 查询、时间窗口、总览计算、商品排行、日趋势和月对比聚合。
- 总览逻辑在 `get_finance_overview` 与 `_build_overview` 中重复。
- 趋势与月对比的分桶逻辑是纯计算，但嵌在异步数据库服务中，无法独立覆盖边界场景。
- `migrate_service.py` 与 `transaction_service.py` 分别为 298、299 行；迁移服务紧邻清库导入，交易服务适合抽离的纯逻辑过少。
- 工作区已有用户未提交的自动同步、账号恢复、迁移和 datetime 告警修复，阶段 3E 不修改或提交这些既有变更。

## 方案比较

### 方案 A：抽离完整财务纯计算层

抽离月份范围、总览、商品排行、日趋势和月对比计算；服务保留查询和时间窗口。计算职责完整、可独立测试且不触碰事务。采用。

### 方案 B：只抽离总览计算

改动最少，但趋势、月对比和商品排行仍与数据库耦合，无法形成稳定领域边界，且不能消除大部分聚合复杂度。不采用。

### 方案 C：优先拆迁移记录清洗器

`_clean_record` 是纯逻辑，但迁移模块同时执行全量清理与恢复，当前工作区又在修改数据库迁移，冲突和数据风险高。不采用。

## 模块结构

新增 `app/services/finance_calculations.py`：

- `month_range(date)`：计算月份起止。
- `build_overview(current, previous, cur_expense, prev_expense)`：生成总收入、总成本、利润、利润率、笔数和环比。
- `build_product_profit_stats(trades)`：按商品聚合收入、利润、笔数和利润率并按利润降序排列。
- `build_daily_trend(trades, expenses, start, end)`：构建连续日期序列并计入运营支出。
- `build_monthly_comparison(trades, expenses, start_year, start_month, months)`：按自然月聚合并处理跨年。

`finance_service.py` 保留：

- 当前时间和查询范围计算。
- Transaction、OperatingExpense、Customer 的 SQL 查询。
- 调用纯计算函数并返回结果。

## 依赖规则

- 计算模块只依赖 Python 标准库和既有 `utils.helpers.round2`。
- 禁止导入 SQLAlchemy、AsyncSession、ORM 模型、FastAPI 或其他服务。
- 计算函数接收具有所需属性的序列，不引入 DTO、协议类或新领域模型。
- `finance_service.py` 单向依赖计算模块，计算模块不得反向依赖服务。
- `get_finance_overview`、`get_product_profit_stats`、`get_customer_value_stats`、`get_finance_overview_by_range`、`get_trend`、`get_monthly_comparison` 和客户计数函数的路径与签名不变。

## 行为兼容

- 总成本继续等于商品成本加运营支出，总利润继续等于收入减总成本。
- 上期为零时，当前大于零的环比仍为 `1.0`，否则为 `0.0`。
- 商品排行继续按总利润降序，字段名与两位小数规则不变。
- 日趋势继续返回含首尾日期的连续自然日序列，无数据日期补零。
- 运营支出继续增加成本并等额减少利润。
- 月对比继续从指定起始年月生成连续 `months` 个自然月，展示名保持 `N月`。
- 本月/上月、自定义范围和 SQL 过滤边界保持不变。

## 测试策略

新增 `test_finance_calculations.py`：

1. 动态检查新模块，在缺失时以断言失败建立 RED 基线。
2. 使用 `SimpleNamespace` 覆盖总览与零基数环比。
3. 覆盖商品聚合、排序和利润率。
4. 覆盖跨日趋势、运营支出和无数据补零。
5. 覆盖跨年月份序列及月度运营支出。
6. 用 AST 断言计算函数归属新模块，且不依赖 SQLAlchemy、ORM 或服务层。

现有 `test_expense_finance_service.py` 保持原状，继续提供数据库集成保护；因该文件已有用户未提交修改，本阶段不编辑它。

## 实施顺序

1. 新增纯计算契约测试并确认模块缺失导致预期 RED。
2. 创建 `finance_calculations.py`，原样迁移并整合计算逻辑。
3. 修改 `finance_service.py`，保留查询与窗口编排并调用计算模块。
4. 运行纯计算、财务集成和财务路由测试，再执行全量回归。
5. 重建后端容器，验证财务只读端点、Alembic 和备份。

## 脏工作区保护

- 提交时仅暂存阶段 3E 的设计、计划、计算模块、财务服务和新测试。
- 不暂存或格式化其他已修改文件。
- 若现有改动导致基线或全量验证失败，先定位归属，不覆盖用户修改。

## 回滚

本阶段不修改数据库、迁移、路由或前端。回退实现提交即可恢复服务内计算，不需要数据回滚。

## 非目标

- 不修改财务统计口径或 API 字段。
- 不重写 SQL 为数据库聚合。
- 不拆迁移或交易服务。
- 不抽象通用聚合框架。
- 不处理工作区中的自动同步、账号恢复、迁移或 datetime 改动。

## 验收标准

- 财务纯计算逻辑归属独立模块，服务层仅负责查询和时间窗口。
- 计算模块无 SQLAlchemy、ORM 或数据库依赖。
- 新计算测试、现有财务集成测试和后端全量测试通过。
- 前端测试、类型检查与生产构建通过。
- 后端容器财务只读端点返回 200，Alembic 与备份校验正常。
- 用户原有未提交改动保持存在且未被纳入阶段 3E 提交。
