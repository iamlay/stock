# 个股股息率模块开发计划（V2 · 全市场）

> 在现有 ETF 投研台上增加 A 股个股模块：覆盖全市场、按股息率排序、用户可自行添加自选、默认排除 ST。
>
> 这是 V2 扩展，不改变当前 ETF MVP 的范围与已上线功能。

---

## 1. 已确认决策

| 决策 | 结论 |
|---|---|
| 覆盖范围 | 全市场 A 股（沪深主板 / 创业板 / 科创板） |
| 用户添加 | 用户可输入任意 A 股代码加入自选 |
| 股息率口径 | **TTM 优先**，详情同时展示最近年度 |
| ST | **默认排除**，可手动切换显示 |
| 市场 | 只做 A 股，不做港股/美股 |
| 行情频率 | 首版日频 EOD；不做个股 5 分钟 |
| 数据来源 | 全市场快照 + 分红批量；个股 K 线按需拉取 |

> “用户添加”定义为加入**个人自选**，不是把股票加进全站股票池。全市场本身已覆盖，用户添加只是收藏。

---

## 2. 产品目标

### 2.1 用户能做什么

- 打开「高股息」列表，查看全市场股票按股息率排序；
- 按行业、市值、最低股息率、是否 ST 筛选；
- 输入股票代码，加入自己的自选；
- 查看单只股票的股息率、市值、PE/PB、分红历史和价格走势；
- 切换排序：TTM 股息率 / 年度股息率 / 市值 / 涨跌幅 / PE。

### 2.2 明确不做

- 不荐股、不给买卖点、不做收益承诺；
- 不做交易、不做组合下单；
- 首版不做港股、美股、北交所；
- 首版不做个股 5 分钟行情；
- 首版不做财务指标深度分析（ROE、现金流等后续再加）。

---

## 3. 架构

```text
全市场股票列表 / 快照 / 分红（批量）
        │
   ETL（每日收盘后）
        │
 stock_profiles / stock_dividends / stock_metrics
        │
   FastAPI /stocks 排序 + 分页
        │
   Next.js /stocks 列表 + /stocks/[code] 详情
        │
   用户自选 stock_watchlist
```

关键设计：

- **全市场排序只依赖 `stock_metrics`**，不依赖 10 年 K 线；
- 个股 K 线按需拉取，只缓存被查看/自选的股票；
- 用户添加自选时，如果代码不在库中，后端自动补股票档案和指标；
- 每日 ETL 更新全市场快照 + 分红 + 指标，单只股票 K 线可异步补。

---

## 4. 数据模型

### 4.1 `instruments`

复用现有表，`type = "stock"`。

### 4.2 `stock_profiles`

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | PK, FK instruments | 6 位代码 |
| `name` | varchar(64) | 名称 |
| `industry` | varchar(32) | 一级行业，用于筛选 |
| `industry_path` | varchar(128) | 完整三级路径 |
| `industry_source` | varchar(16) | eastmoney / sina / null |
| `industry_updated_at` | timestamptz | |
| `market` | varchar(16) | 主板 / 创业板 / 科创板 |
| `is_st` | boolean | ST/*ST |
| `list_date` | date | 上市日 |
| `total_shares` | numeric | 总股本 |
| `status` | varchar(16) | active / suspended / delisted |
| `updated_at` | timestamptz | |

### 4.3 `stock_dividends`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | PK | |
| `code` | FK | |
| `ex_date` | date | 除权除息日 |
| `fiscal_year` | int | 所属年度 |
| `cash_per_share` | numeric(12,6) | 每股现金（税前） |
| `plan` | varchar(128) | 方案原文 |
| `is_special` | boolean | 特别分红 |
| `source` | varchar(16) | eastmoney/manual |
| `created_at` | timestamptz | |

唯一约束：`(code, ex_date, plan)`。

### 4.4 `stock_metrics`

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | PK, FK | |
| `price` | numeric | 最新价 |
| `change_pct` | numeric | 当日涨跌 |
| `market_cap` | numeric | 总市值（亿元） |
| `pe_ttm` | numeric | |
| `pb` | numeric | |
| `dividend_yield_ttm` | numeric | TTM 股息率 % |
| `dividend_yield_fy` | numeric | 最近完整年度 % |
| `last_ex_date` | date | 最近除息日 |
| `updated_at` | timestamptz | |

索引：

```text
(dividend_yield_ttm DESC)
(dividend_yield_fy DESC)
(market_cap DESC)
(industry)
```

### 4.5 `stock_watchlist`

| 字段 | 类型 |
|---|---|
| `id` | PK |
| `user_id` | FK users |
| `code` | FK instruments |
| `created_at` | timestamptz |

唯一约束：`(user_id, code)`。

### 4.6 `stock_detail_cache`（可选）

缓存个股 K 线拉取时间，避免重复请求：

```text
code, last_synced_at, bars_count, status
```

---

## 5. 全市场数据源策略

全市场约 5,000+ 只股票，不能沿用 ETF 的“每只股票单独同步 10 年”方式。

> Phase 0 实测：Eastmoney 列表接口在当前网络会被断连，Sina `hs_a` 兜底可用（5,217 只），但**没有行业字段**；Eastmoney 分红接口、腾讯单股日线可用。详见 [Phase 0 报告](STOCK_PHASE0_REPORT.md)。
>
> 行业 Phase 0 结论：Eastmoney F10 可作主源（15/15 样本，三级行业），但只能逐只/分批；Sina 行业节点可批量但只覆盖 2,927/5,217（56%）。首版采用 **Sina 粗分类 + Eastmoney 按需补全 + 未分类兜底**。详见 [行业 Phase 0 报告](STOCK_INDUSTRY_PHASE0_REPORT.md)。

### 5.1 每日全市场快照

- 用 Eastmoney 批量列表接口分页获取：
  - 代码、名称、最新价、涨跌幅、总市值、PE、PB、行业、ST 标记；
- 每页 100 条，约 50–60 页；
- 一次任务更新 `stock_profiles` 和 `stock_metrics` 的价格/市值/PE/PB。

### 5.2 每日分红数据

- 用 Eastmoney 分红送配批量接口分页拉取；
- 只保留有 `ex_date` 和 `cash_per_share` 的记录；
- 增量更新，按 `(code, ex_date, plan)` 去重；
- 全市场分红记录预计几万到十几万行。

### 5.3 个股 K 线

- 不预拉全市场 10 年日线；
- 用户查看详情或加入自选时，按需拉最近 250 天；
- 已拉过的股票缓存 1 天；
- 全市场排序不依赖 K 线。

> Phase 0 必须验证：批量列表接口、分红接口、单股 K 线接口是否稳定，以及字段是否包含 ST、行业、市值。

---

## 6. 股息率口径

### 6.1 TTM（默认）

```text
TTM 股息率 =
  sum(cash_per_share where ex_date in [today-365, today])
  / latest_close * 100
```

### 6.2 最近年度

```text
年度股息率 =
  sum(cash_per_share where fiscal_year = latest_complete_year)
  / latest_close * 100
```

规则：

- 用**不复权最新价**；
- 只统计已除息；
- 同一除息日多笔分红先合并；
- 特别分红标记但计入；
- 无分红显示 `—`，不显示 0；
- 股息率 > 30% 或 < 0 进质量检查，不参与默认排序；
- 停牌/退市/ST 默认排除。

---

## 7. ETL 与调度

### 7.1 命令

```bash
python -m etl.cli stock-universe
python -m etl.cli stock-daily
python -m etl.cli stock-dividends
python -m etl.cli stock-metrics
python -m etl.cli stock-sync --code 600519
python -m etl.cli stock-status
```

### 7.2 每日流程

```text
18:30 收盘后
  1. stock-universe：更新全市场代码/名称/行业/ST
  2. stock-daily：批量快照，更新价格/市值/PE/PB
  3. stock-dividends：增量分红
  4. stock-metrics：计算 TTM / 年度股息率
  5. 质量检查
```

### 7.3 按需流程

```text
用户添加自选 / 打开详情
  → 检查 stock_metrics 是否存在
  → 不存在则同步单股档案 + 快照 + 分红
  → 详情页再按需拉 250 天 K 线
```

### 7.4 调度

- 每日全市场任务放 GitHub Actions 或 Railway 日任务；
- 不在 5 分钟 Cron 里跑全市场；
- 单股按需同步在 API 请求内完成（限时 3–5 秒），失败则标记待重试。

---

## 8. 后端 API

### 8.1 列表

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
  "total": 5200,
  "page": 1,
  "page_size": 20
}
```

排序白名单校验，NULL 排最后。

### 8.2 详情

```text
GET /api/v1/stocks/{code}
```

返回指标、最近 250 根日线、分红历史、口径说明；首次访问可触发单股同步。

### 8.3 自选

```text
GET    /api/v1/stock-watchlist
POST   /api/v1/stock-watchlist   {"code":"600519"}
DELETE /api/v1/stock-watchlist/{code}
```

添加时：

1. 校验 6 位代码；
2. 不存在则插入 `instruments` / `stock_profiles`；
3. 拉一次快照和分红；
4. 写自选；
5. 限流：每用户每分钟 10 次。

### 8.4 管理接口

```text
GET    /api/v1/admin/stocks
PATCH  /api/v1/admin/stocks/{code}   {"status":"active|excluded"}
POST   /api/v1/admin/stocks/{code}/sync
```

用于手工排除异常股票、强制同步。

---

## 9. 前端

### 9.1 `/stocks` 列表

- 搜索代码/名称；
- 行业筛选；
- 最低股息率；
- 排除 ST 开关；
- 排序：TTM 股息率（默认）/ 年度股息率 / 市值 / 涨跌幅 / PE；
- 表格列：

```text
代码/名称 | 行业 | 最新价 | 股息率TTM | 年度股息率 | 市值 | PE | 状态 | 自选
```

- 分页 20/页；
- 点击表头排序；
- 顶部提示“数据为日频，非实时”。

### 9.2 `/stocks/[code]` 详情

- 价格、涨跌、市值、PE/PB；
- TTM 股息率、年度股息率、最近除息日；
- 分红历史表；
- 近 250 日价格曲线；
- 加入/移出自选；
- 数据来源、更新时间、免责声明。

### 9.3 添加自选

- 列表顶部或详情页「添加股票」；
- 输入 6 位代码；
- 校验 A 股、排除 ST；
- 成功后刷新列表；
- 失败提示：代码不存在/已退市/非 A 股。

### 9.4 管理页

`/admin/stocks`：

- 搜索股票；
- 查看同步状态；
- 手动同步；
- 排除异常股票；
- 查看失败原因。

### 9.5 导航

新增「高股息」入口，放在 ETF 数据之后。

---

## 10. 测试

### 后端

- TTM / 年度股息率计算；
- 无分红、特别分红、重复分红；
- 排序、分页、NULL 最后；
- ST 过滤；
- 用户添加任意代码；
- 自选唯一约束；
- 管理排除；
- 单股同步幂等；
- 权限与限流。

### 前端

- 排序切换；
- 行业/股息率筛选；
- 添加自选；
- 详情分红表；
- 空数据/API 失败；
- build/typecheck。

### 数据

- 抽 20 只股票与交易所公告核对分红；
- 股息率误差 < 0.1 个百分点；
- ST 标记正确；
- 全市场快照覆盖率和最新日期。

---

## 11. 排期

按 1 名全栈开发估算：

| 阶段 | 内容 | 工期 |
|---|---|---|
| Phase 0 | 数据源验证：全市场列表、分红、单股 K 线 | 2–3 天 |
| Phase 1 | 表结构、迁移、全市场 ETL、指标计算 | 5–7 天 |
| Phase 2 | API：列表/详情/自选/管理 | 3–4 天 |
| Phase 3 | 前端列表/详情/添加/管理页 | 4–5 天 |
| Phase 4 | 调度、质量检查、性能、文档 | 3–4 天 |
| 缓冲 | 数据修复、边界情况 | 2–3 天 |

**合计：约 19–26 个工作日（4–5 周）。**

比 50–100 只股票池方案多约 2 周，主要成本在全市场数据管道和性能。

---

## 12. 风险

| 风险 | 影响 | 应对 |
|---|---|---|
| 全市场批量接口限流 | 每日任务失败 | 分页 + 重试 + 断点续跑 |
| 分红数据缺失 | 股息率错误 | 手工 CSV 兜底 + 质量检查 |
| 特别分红 | 排序异常 | 标记 + 30% 上限 |
| 前复权价算股息率 | 高估 | 明确用不复权价 |
| 用户乱加代码 | 无效数据 | 校验 6 位、A 股、限流 |
| 全市场排序性能 | 慢 | `stock_metrics` 索引 + 分页 |
| 单股按需拉取慢 | 详情等待 | 3–5 秒超时 + 后台重试 |
| ST/退市识别 | 展示错误 | 名称/状态双校验，默认排除 |
| 数据授权 | 商用风险 | 确认来源许可，必要时换付费源 |

---

## 13. 验收标准

- [ ] 全市场 5,000+ 只 A 股入库；
- [ ] `/stocks` 默认按 TTM 股息率降序；
- [ ] 无分红显示 `—` 且排最后；
- [ ] 默认排除 ST，可切换；
- [ ] 用户输入任意 A 股代码可加入自选；
- [ ] 详情页展示 TTM/年度股息率、分红历史、价格曲线；
- [ ] 管理后台可排除、同步；
- [ ] 每日收盘后自动更新；
- [ ] `pytest` / `ruff` / `next build` 通过；
- [ ] 页面有数据来源、更新时间、免责声明。

---

## 14. 实施顺序

1. **Phase 0 数据源验证**：确认全市场列表、分红、单股 K 线字段；
2. 建表 + 迁移；
3. 全市场快照 + 分红 + 指标 ETL；
4. API 列表/详情/自选；
5. 前端列表/详情/添加；
6. 调度 + 质量检查 + 性能优化；
7. 灰度 500 只，再扩到全市场。

> 不建议一上来跑全市场 5,000 只。先用 500 只验证数据质量和性能，再扩量。
