# 个股模块 Phase 1 实施报告

> 日期：2026-10-20
> 范围：表结构、迁移、全市场 ETL、500 只灰度
> 结论：**数据链路已跑通，500 只灰度完成；下一步接 API 和前端。**

---

## 1. 已完成

| 项 | 状态 |
|---|---|
| 表结构 | ✅ `stock_profiles` / `stock_dividends` / `stock_metrics` / `stock_watchlist` |
| 迁移 | ✅ `5f4740869b51_stock_dividend_module` |
| 全市场列表 | ✅ 新浪 `hs_a`，5,217 只 |
| 500 只灰度 | ✅ 按市值取前 500 |
| 分红同步 | ✅ 500 只，7,181 条 |
| TTM 指标 | ✅ 431 只有股息率 |
| 单股同步 | ✅ `stock-sync --code` |
| 测试 | ✅ 93 passed |

---

## 2. 数据模型

### `stock_profiles`

```text
code, industry, industry_path, industry_source,
market, is_st, list_date, total_shares, status
```

### `stock_dividends`

```text
id, code, ex_date, fiscal_year, cash_per_share,
plan, is_special, source, created_at
```

唯一约束：`(code, ex_date, plan)`。

### `stock_metrics`

```text
code, price, change_pct, market_cap, pe_ttm, pb,
dividend_yield_ttm, dividend_yield_fy, last_ex_date, updated_at
```

### `stock_watchlist`

```text
id, user_id, code, created_at
```

唯一约束：`(user_id, code)`。

---

## 3. 灰度结果

执行：

```bash
python -m etl.cli stock-universe --limit 500
python -m etl.cli stock-dividends --limit 500 --delay 0.15
```

结果：

```text
stocks profiles=500 metrics=500 dividends=7181 with_yield=431 st=0
```

- 500 只全部有行情和市值；
- 431 只有 TTM 股息率；
- 69 只无分红或数据缺失，显示 `—`；
- 0 只 ST（按市值前 500 未包含 ST，符合预期）。

### 股息率前 10

| 股票 | 代码 | TTM 股息率 | 最新价 | 市值（亿） |
|---|---|---|---|---|
| 格力电器 | 000651 | 7.77% | 38.60 | 2,162 |
| 中国平安 | 601318 | 7.19% | 51.20 | 9,271 |
| 五粮液 | 000858 | 7.08% | 72.85 | 2,828 |
| 中远海控 | 601919 | 6.01% | 16.63 | 2,531 |
| 中国建筑 | 601668 | 6.00% | 4.53 | 1,872 |
| 海尔智家 | 600690 | 5.77% | 20.11 | 1,870 |
| 兴业银行 | 601166 | 5.76% | 18.51 | 3,917 |
| 光大银行 | 601818 | 5.70% | 3.07 | 1,814 |
| 中国中车 | 601766 | 5.36% | 6.34 | 1,820 |
| 平安银行 | 000001 | 5.32% | 11.44 | 2,220 |

---

## 4. ETL 命令

```bash
# 全市场或前 N 只
python -m etl.cli stock-universe --limit 500

# 分红（按市值顺序）
python -m etl.cli stock-dividends --limit 500

# 重算 TTM / 年度股息率
python -m etl.cli stock-metrics --limit 500

# 单只股票
python -m etl.cli stock-sync --code 600519

# 一键灰度
python -m etl.cli stock-pilot --limit 500 --dividend-limit 500

# 状态
python -m etl.cli stock-status
```

---

## 5. 已知限制

| 问题 | 影响 | 处理 |
|---|---|---|
| 行业字段为空 | 行业筛选不可用 | Phase 1.5 补 Eastmoney F10 |
| 只灰度 500 只 | 不是全市场 | 扩量前先验证数据质量 |
| 分红来自 Eastmoney | 接口可能限流 | 已逐只捕获错误，可断点重跑 |
| 无 K 线 | 详情页暂无走势图 | Phase 2 按需拉取 |
| 无 API/前端 | 用户还看不到 | Phase 2/3 |
| 无自选接口 | 不能收藏 | Phase 3 |

---

## 6. 数据质量结论

- 分红记录 7,181 条，无重复（唯一约束生效）；
- TTM 计算已排除未来除息日；
- 无分红股票不显示 0，保留 `—`；
- 500 只全部有价格和市值；
- 前 10 股息率与常识基本一致，但需要人工抽核高股息样本。

建议抽核：

```text
000651 格力电器
601318 中国平安
000858 五粮液
601919 中远海控
601668 中国建筑
```

重点检查是否包含特别分红、中期分红。

---

## 7. 下一步

1. **Phase 1.5**：补行业（Eastmoney F10，优先 500 只）；
2. **Phase 2**：
   - `GET /api/v1/stocks` 排序/分页/筛选；
   - `GET /api/v1/stocks/{code}` 详情；
   - 管理端同步/排除；
3. **Phase 3**：
   - 用户自选；
   - 前端 `/stocks`、`/stocks/[code]`；
   - 添加到导航；
4. 扩到 5,000 只前，先跑一周 500 只，观察分红缺失率和接口稳定性。
