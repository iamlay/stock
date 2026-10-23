# 个股全市场扩量报告

> 日期：2026-10-21
> 范围：从 500 只扩到 5,000 只 A 股
> 结论：**本地全市场链路验证通过，等待生产执行。**
> 注：当前分红默认已扩展到 3650 天；本文中的 730 天与 14,000 条为当时快照。

---

## 1. 扩量方式

不再逐只拉 5,000 次分红，改为：

```text
stock-universe --limit 5000     # 一次新浪列表
stock-dividends-bulk --days 730 # 29 页批量分红
stock-industry --sina-only      # 49 个行业节点
```

本地结果：

```text
stocks universe=5217 stored=5000
stock dividends bulk codes=5000 records=9841 written=7783 metrics=5000
stock industry selected=5000 sina=5000 eastmoney=0 errors=0
stocks profiles=5000 metrics=5000 dividends=14964 with_yield=3404 st=127
```

---

## 2. 数据结果

| 项 | 数量 |
|---|---|
| 股票档案 | 5,000 |
| 指标 | 5,000 |
| 分红记录 | 14,964 |
| 有 TTM 股息率 | 3,404 |
| ST | 127 |
| 有行业 | 5,000 |

说明：

- 3,404 只有股息率，约 68%；
- 其余无分红或近两年无实施分红；
- 行业使用新浪申万一级（31 个节点），5,000 只全部覆盖；
- 如需更细行业，可再用 Eastmoney F10 补三级路径。

---

## 3. 批量分红接口

Eastmoney `RPT_SHAREBONUS_DET` 支持按除息日过滤：

```text
filter=(EX_DIVIDEND_DATE>='2024-01-01')
pageSize=500
```

两年数据约 29 页、14,000 条，耗时远低于逐只请求。

---

## 4. 生产工作流

新增：

```text
.github/workflows/stock-full.yml
```

Actions → Stock Full Market → Run workflow：

```text
limit: 5000
days: 730
```

执行：

```bash
python -m etl.cli stock-universe --limit 5000
python -m etl.cli stock-dividends-bulk --days 730
python -m etl.cli stock-industry --limit 5000 --sina-only --sina-prefix sw_ --overwrite --sina-prefix sw_ --overwrite
python -m etl.cli stock-status
```

预计 3–5 分钟。

---

## 5. 后续定时

| 工作流 | 频率 | 内容 |
|---|---|---|
| `etl.yml` | 工作日 18:30 | 5,000 只价格/市值/PE/PB + 股息率重算 |
| `stock-dividends.yml` | 周一 19:00 | 批量分红增量 |
| `stock-full.yml` | 手动 | 全市场初始化 |
| `stock-industry` | 手动/季度 | 申万一级行业（5,000 只全量） |

---

## 6. 已知限制

- 行业是申万一级 31 类，粒度较粗；
- 5,000 只价格来自 Sina 快照，不是实时；
- 无 K 线的股票占多数，K 线按需生成；
- 全市场分红只拉近两年，更早历史不展示；
- 新上市股票需要重跑 `stock-universe`。

---

## 7. 验收标准

- [ ] `/api/v1/stocks` 返回 `total >= 5000`；
- [ ] 首页按 TTM 股息率有值；
- [ ] 最高股息率前 10 合理；
- [ ] `/stocks` 分页可翻到最后一页；
- [ ] 行业筛选只返回有行业的股票；
- [ ] 详情页能打开任意代码；
- [ ] `stock-daily` 能更新 5,000 只。
