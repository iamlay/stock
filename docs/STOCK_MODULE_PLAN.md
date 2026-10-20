# 个股股息率模块开发计划（V2）

> 目标：在现有 ETF 投研台上增加 A 股个股模块，支持维护股票池、按股息率排序、查看个股详情与股息历史。
>
> 这是 V2 扩展，不改变当前 ETF MVP 的范围与已上线功能。

---

## 1. 产品目标

### 1.1 用户价值

- 找到高股息股票，而不是只看 ETF；
- 按股息率、市值、行业筛选；
- 查看一只股票的历史分红、当前股息率、估值；
- 把关注的股票加入自选。

### 1.2 明确不做

- 不荐股、不提供买卖点、不做收益承诺；
- 不做交易、不做组合下单；
- 首版不做港股、美股、北交所；
- 首版不做实时 5 分钟个股行情，先日频 EOD；
- 首版不做全市场 5000 只，先维护 50–100 只股票池。

### 1.3 推荐范围

| 项 | 首版 |
|---|---|
| 市场 | 沪深 A 股 |
| 股票池 | 管理员维护 50–100 只 |
| 行情 | 日线 EOD |
| 股息率 | TTM 税前现金分红 / 最新价 |
| 排序 | 股息率、市值、涨跌幅、PE |
| 用户操作 | 加入/移出自选 |
| 管理操作 | 添加、停用、手动同步 |

---

## 2. 需要先确认的决策

| 决策 | 选项 | 建议 |
|---|---|---|
| 谁能添加股票 | 管理员 / 所有用户 | **管理员维护股票池**，用户只加自选 |
| 股息率口径 | TTM / 最近完整年度 | **默认 TTM，详情同时展示年度** |
| 价格口径 | 前复权 / 不复权 | 股息率用**不复权最新价**，K 线用前复权 |
| 是否含特别股息 | 含 / 不含 | 含，但在明细中标注“特别分红” |
| 是否排除 ST | 排除 / 可切换 | 默认排除，提供开关 |
| 首版股票数量 | 20 / 50–100 | **50–100**，避免全市场数据质量风险 |

---

## 3. 数据模型

### 3.1 `instruments`

复用现有表，新增 `type = "stock"`，`exchange` 为 `SH` / `SZ`。

### 3.2 `stock_profiles`

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | PK, FK instruments | 股票代码 |
| `industry` | varchar(32) | 申万/东财行业 |
| `market` | varchar(16) | 主板/创业板/科创板 |
| `is_st` | boolean | 是否 ST/*ST |
| `list_date` | date | 上市日 |
| `total_shares` | numeric | 总股本 |
| `updated_at` | timestamptz | |

### 3.3 `stock_dividends`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | PK | |
| `code` | FK instruments | |
| `ex_date` | date | 除权除息日 |
| `fiscal_year` | int | 所属年度 |
| `cash_per_share` | numeric(12,6) | 每股现金分红（税前） |
| `plan` | varchar(128) | 分红方案原文 |
| `is_special` | boolean | 是否特别分红 |
| `source` | varchar(16) | eastmoney/manual |
| `created_at` | timestamptz | |

唯一约束：`(code, ex_date, plan)`，防止重复导入。

### 3.4 `stock_metrics`

物化指标表，API 直接排序，避免每次实时聚合。

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | PK, FK | |
| `price` | numeric | 最新价 |
| `change_pct` | numeric | 当日涨跌 |
| `market_cap` | numeric | 总市值（亿元） |
| `pe_ttm` | numeric | |
| `pb` | numeric | |
| `dividend_yield_ttm` | numeric | 近 12 个月股息率 % |
| `dividend_yield_fy` | numeric | 最近完整年度股息率 % |
| `last_ex_date` | date | 最近除息日 |
| `updated_at` | timestamptz | |

索引：`(dividend_yield_ttm DESC)`、`(market_cap DESC)`、`(industry)`。

### 3.5 `stock_watchlist`

| 字段 | 类型 |
|---|---|
| `id` | PK |
| `user_id` | FK users |
| `code` | FK instruments |
| `created_at` | timestamptz |

唯一约束：`(user_id, code)`。

---

## 4. 数据源与口径

### 4.1 行情

- 日线：现有 Eastmoney `push2his` 为主，Tencent 兜底；
- 股票代码可直接复用 `secid_for` / `symbol_for`；
- 日线存 `market_daily`，与 ETF 共用；
- 最新价、PE、PB、市值：Tencent 批量报价或 Eastmoney 快照。

### 4.2 分红

优先级：

1. Eastmoney 分红送配接口（`RPT_SHAREBONUS_DET` / F10）；
2. 备用：交易所公告/手工 CSV 导入；
3. 必须有 `ex_date` 和 `cash_per_share`，否则不入库。

### 4.3 股息率公式

```text
TTM 股息率 =
  sum(cash_per_share where ex_date in [today-365, today])
  / latest_close * 100

最近年度股息率 =
  sum(cash_per_share where fiscal_year = latest_complete_year)
  / latest_close * 100
```

规则：

- 用**不复权最新价**，避免前复权价格把股息率算高；
- 只统计已除息（`ex_date <= today`）；
- 同一 `ex_date` 多笔分红先合并；
- 特别分红单独标记，但仍计入；
- 股息率 > 30% 或 < 0 视为异常，写入质量检查，不直接展示排序；
- 无分红显示 `—`，不显示 0。

---

## 5. ETL 设计

### 5.1 新增命令

```bash
python -m etl.cli sync-stock --code 600519
python -m etl.cli sync-stocks
python -m etl.cli stock-status
```

### 5.2 流程

```text
1. 读取股票池（instruments.type=stock）
2. 拉日线 → market_daily
3. 拉分红 → stock_dividends
4. 拉快照 → price / PE / PB / 市值
5. 计算 stock_metrics
6. 写 data_jobs / data_quality_checks
```

### 5.3 调度

- 每日 18:30 随现有 ETL 一起跑；
- 先做日频，不做 5 分钟个股报价；
- 管理员添加股票后立即触发一次 `sync-stock`；
- 失败只影响该股票，不阻断其他股票。

### 5.4 质量检查

- 日线行数、最新日期；
- 分红记录数、最近除息日；
- 股息率是否在 0–30%；
- 市值/PE 是否为正；
- ST 标记是否更新。

---

## 6. 后端 API

### 6.1 公开接口

```text
GET /api/v1/stocks
  ?sort=dividend_yield_ttm|dividend_yield_fy|market_cap|change_pct|pe_ttm
  &order=desc|asc
  &q=
  &industry=
  &min_yield=
  &include_st=false
  &page=1
  &page_size=20
```

响应：

```json
{
  "items": [
    {
      "code": "600519",
      "name": "贵州茅台",
      "industry": "食品饮料",
      "price": 1500.0,
      "change_pct": 1.2,
      "market_cap": 18800.0,
      "pe_ttm": 22.1,
      "pb": 8.2,
      "dividend_yield_ttm": 3.4,
      "dividend_yield_fy": 3.1,
      "last_ex_date": "2026-06-20",
      "is_st": false
    }
  ],
  "total": 80,
  "page": 1,
  "page_size": 20
}
```

```text
GET /api/v1/stocks/{code}
```

返回指标、最近 250 根日线、分红历史、股息率说明。

### 6.2 用户自选

```text
GET    /api/v1/stock-watchlist
POST   /api/v1/stock-watchlist   {"code":"600519"}
DELETE /api/v1/stock-watchlist/{code}
```

### 6.3 管理后台

```text
GET    /api/v1/admin/stocks
POST   /api/v1/admin/stocks          {"code":"600519","industry":"食品饮料"}
PATCH  /api/v1/admin/stocks/{code}   {"is_active":false}
POST   /api/v1/admin/stocks/{code}/sync
```

权限沿用 `role=admin`，操作写 `admin_audit_logs`。

---

## 7. 前端

### 7.1 `/stocks` 个股列表

- 顶部：搜索框、行业筛选、最低股息率、排除 ST；
- 排序下拉：股息率 TTM / 最近年度 / 市值 / 涨跌幅 / PE；
- 表格列：

```text
代码/名称 | 行业 | 最新价 | 股息率 TTM | 年度股息率 | 市值 | PE | 状态 | 自选
```

- 点击表头切换排序；
- 分页；
- 空状态与数据延迟提示。

### 7.2 `/stocks/[code]` 详情

- 价格、涨跌、市值、PE/PB；
- 股息率卡片：TTM、最近年度、最近除息日；
- 分红历史表：年度、除息日、每股现金、方案；
- 年度分红柱状图；
- 近 250 日价格曲线；
- 加入自选按钮；
- 数据来源与口径说明。

### 7.3 `/admin/stocks`

- 添加股票代码；
- 查看同步状态、最近更新时间；
- 手动同步；
- 停用/恢复；
- 失败原因。

### 7.4 导航

新增「高股息」或「个股」入口，放在 ETF 数据之后。

---

## 8. 测试计划

### 后端

- 股息率公式：TTM、年度、无分红、特别分红、重复分红；
- 排序：股息率降序、NULL 放最后；
- 分页、搜索、行业筛选、ST 过滤；
- 管理员添加股票、重复添加、停用；
- 用户自选唯一约束；
- ETL 单股票同步幂等；
- 权限：普通用户不能调 admin 接口。

### 前端

- 列表排序切换；
- 详情分红表；
- 自选加入/移除；
- 空数据与 API 失败回退；
- build / typecheck。

### 数据验收

- 抽 10 只股票，与交易所公告/东财人工核对分红；
- 股息率误差 < 0.1 个百分点；
- 最近除息日正确；
- ST 标记正确。

---

## 9. 里程碑与排期

按 1 名全栈开发估算：

| 阶段 | 内容 | 工期 |
|---|---|---|
| Phase 0 | 数据源验证：10 只股票分红/行情抓取 | 1–2 天 |
| Phase 1 | 表结构、迁移、ETL、admin API、列表 API | 3–4 天 |
| Phase 2 | 前端列表、详情、排序筛选、管理页 | 3–4 天 |
| Phase 3 | 自选、每日调度、质量检查、文档 | 2 天 |
| 缓冲 | 数据修复、边界情况 | 1–2 天 |

**合计：约 9–12 个工作日（2–2.5 周）。**

---

## 10. 风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| 分红接口不稳定 | 数据缺失 | 手工 CSV 导入兜底 |
| 特别分红导致股息率异常 | 排序失真 | 标记 + 质量检查 + 上限 |
| 停牌/ST/退市 | 展示错误 | 默认排除 ST，停牌标记 |
| 前复权价格算股息率 | 高估 | 明确用不复权价 |
| 股票池扩张过快 | 数据质量下降 | 首版 50–100 只 |
| 合规风险 | 被理解为荐股 | 只做数据与排序，不做建议，保留免责声明 |
| 数据授权 | 商用风险 | 确认来源许可，必要时换付费源 |

---

## 11. 验收标准

- [ ] 管理员可添加 600519、601398 等股票；
- [ ] ETL 能同步日线、分红、市值、PE；
- [ ] `/stocks` 默认按股息率 TTM 降序；
- [ ] 无分红股票显示 `—` 且排在最后；
- [ ] 详情页能看最近 3 年分红；
- [ ] 用户可加入/移出自选；
- [ ] 管理后台可停用、手动同步；
- [ ] 所有接口有测试，`pytest` / `ruff` / `next build` 通过；
- [ ] 页面标注数据来源、更新时间、免责声明。

---

## 12. 建议的实施顺序

1. 先做 **Phase 0 数据源验证**，确认分红字段和 10 只样本；
2. 确认后再建表，避免按错误字段返工；
3. 先 API + 管理端，再接前端；
4. 首版只做 50 只，跑一周数据质量后再扩；
5. 股息率排序稳定后，再考虑 5 分钟报价和港股/美股。

---

## 13. 待确认问题

1. 股票池由管理员维护，还是允许用户自己添加？
2. 股息率默认用 TTM 还是最近完整年度？
3. 首版是否排除 ST？
4. 是否需要港股/美股？
5. 是否接受首版只覆盖 50–100 只，而不是全市场？

> 建议默认：管理员维护、TTM 优先、排除 ST、只做 A 股、首版 50–100 只。
