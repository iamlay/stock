# ETL

数据采集、校验与入库。W2 已完成日线管道，W3 扩展估值、份额与宏观。

## 数据源

| 优先级 | 来源 | 说明 |
|---|---|---|
| 主 | 东方财富 `push2his` | 前复权日线，字段全（含成交额、振幅） |
| 备 | 腾讯 `web.ifzq.gtimg.cn` | 前复权日线，按年份分页；历史段无成交额 |
| 快照 | 腾讯 `qt.gtimg.cn` | 一次批量拉 20 只：最新价、成交额、总市值/份额 |

`etl.pipeline._fetch_series` 先试东财，失败自动切腾讯，并把实际来源写入 `market_daily.source`。
实际运行中若东财对 IP 限流，整批数据会落到 `tencent`，属预期行为。

## 命令

```bash
# 1) 建表（PostgreSQL）
alembic -c apps/api/alembic.ini upgrade head

# 2) 写入 20 只 ETF 字典与分类
python -m etl.cli seed

# 3) 同步
python -m etl.cli sync --codes 510300,512890 --start 2016-01-01
python -m etl.cli sync-all --start 2016-01-01 --delay 0.2
python -m etl.cli sync-shares

# 4) 查看
python -m etl.cli status
python -m etl.cli quality --limit 20
```

数据库连接通过 `STOCKLAB_DATABASE_URL` 覆盖，默认
`postgresql+psycopg://stocklab:stocklab@127.0.0.1:5432/stocklab`。

## 幂等与对账

- 每只标的一次同步 = 删除 `[首日, 末日]` 窗口后整段重插，重复运行不会产生重复行。
- 每次同步写一条 `data_jobs`，成功/失败/耗时/行数可查。
- 每个批次写 7–8 条 `data_quality_checks`（有 freshness 时 8 条）。

## 质量规则

| 检查 | 说明 | 失败级别 |
|---|---|---|
| `non_empty` | 返回行数 > 0 | fail |
| `row_count` | ≥ 250 行 | warn |
| `unique_dates` | 交易日不重复 | fail |
| `date_order` | 日期严格升序 | fail |
| `ohlc_bounds` | `high >= low`，`close` 在高低之间 | fail |
| `price_positive` | 价格 > 0 | fail |
| `volume_non_negative` | 成交量 ≥ 0 | fail |
| `freshness` | 最新日与预期交易日相差 ≤ 7 天 | warn |
| `quotes_complete` | 快照覆盖全部目标标的 | warn |
| `positive_aum` | 规模 > 0 | fail |
| `positive_price` | 快照价格 > 0 | fail |

## 已知限制（W4 处理）

- 腾讯历史日线无成交额；`sync-shares` 会用当日快照补一根带成交额的 `market_daily`。
- `adj_factor` 暂固定为 1，因为源数据已是前复权；后复权与分红再投在回测层处理。
- 交易日历由 ETF 日线并集生成，尚未接入交易所官方日历。
- 尚未做定时调度；W4 接入 Celery Beat（15:30 日线、18:00 份额）。
- 指数估值（PE/PB/分位）与宏观数据尚未接入。
