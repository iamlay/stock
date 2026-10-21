# 个股数据质量检查

> 日期：2026-10-21
> 范围：5,000 只个股的股息率、价格、行业、分红、更新时效

---

## 1. 检查项

| 检查 | 级别 | 规则 |
|---|---|---|
| `price_missing` | fail | 最新价为空或 ≤0 |
| `yield_extreme` | fail | TTM 股息率 > 30% |
| `yield_high` | warn | TTM 股息率 > 15% |
| `ttm_fy_divergence` | warn | TTM 与年度股息率相差 > 5 个百分点 |
| `industry_missing` | warn | 行业为空 |
| `stale_metrics` | warn | 指标超过 3 天未更新 |
| `future_dividends` | warn | 存在未来除息日记录 |
| `duplicate_dividends` | fail | 同一 code + 除息日 + 方案重复 |

---

## 2. 命令

```bash
python -m etl.cli stock-quality --limit 5000
python -m etl.cli stock-quality --limit 5000 --write
```

输出：

```text
stock quality metrics=5000 st=128 issues=... fail=... warn=...
  FAIL yield_extreme       count=...
  WARN yield_high          count=...
  WARN ttm_fy_divergence   count=...
  WARN industry_missing    count=...
  WARN stale_metrics       count=...
top yields:
  603165 荣晟环保 ttm=... fy=... price=...
```

`--write` 会把结果写入：

- `data_jobs`（job_name=`stock_quality`）
- `data_quality_checks`

报告文件：

```text
etl/out/stock_quality.json
```

---

## 3. 工作流

```text
.github/workflows/stock-quality.yml
```

- 手动：Actions → Stock Quality → Run workflow
- 定时：每周一 20:00（北京时间），在分红刷新之后

---

## 4. 重点核查样本

当前高股息前几名：

```text
荣晟环保  16.05%
冰川网络  14.02%
海澜之家  11.60%
达仁堂    11.47%
汇洁股份  11.35%
```

需要人工确认：

- 是否包含多次中期分红；
- 是否包含特别分红；
- 年度 vs TTM 差异是否合理；
- 价格是否为不复权价；
- 分红是否长期可持续。

---

## 5. 后续

- 对 `yield_extreme` 增加人工复核标记；
- 对特别分红单独展示；
- 把质量检查结果接入后台页面；
- 连续 3 天同一告警才通知，避免噪声。
