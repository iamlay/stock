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

## 4. 生产快照（2026-10-21）

基于公开 API 全量拉取 4,872 只非 ST：

```text
行业为空        0
价格为空        0
TTM > 15%       1
TTM > 30%       0
TTM/年度差异>5  24
```

高股息前 5：

```text
603165 荣晟环保  16.05%  TTM / 4.63% 年度
300533 冰川网络  14.02%  TTM / 14.02% 年度
600398 海澜之家  11.60%  TTM / 4.61% 年度
600329 达仁堂    11.47%  TTM / 11.47% 年度
002763 汇洁股份  11.35%  TTM / 15.60% 年度
```

注意：年度股息率仍在旧口径（当前年度中期分红），下一次 `stock-daily` 或 `stock-quality` 工作流会先重算。

---

## 5. 分红标记与可持续性

### 分红标记

`stock_dividends` 增加：

```text
is_special   方案含“特别”
is_one_off   特别分红，或单次现金/价格 >= 8%
```

详情页会显示：

```text
特别
单次大额
```

### 股票级提示

`stock_metrics.sustainability`：

| 值 | 含义 |
|---|---|
| `stable` | 连续 5 年以上分红，股息率 ≤ 8% |
| `normal` | 常规分红 |
| `watch` | 股息率 > 10% 或 TTM/年度差异大 |
| `one_off` | 含特别或单次大额分红 |
| `high_yield` | TTM > 15%，需核查 |
| `none` | 近两年无现金分红 |

列表页在股息率下方显示：

```text
连续 / 核查 / 单次大额 / 高股息 / 无分红
```

---

## 6. 告警

`stock-quality --fail-on-fail` 在出现 `fail` 时返回非零，GitHub Actions 任务失败，默认会通知仓库关注者。

可选 Webhook：

```text
Secret: STOCKLAB_ALERT_WEBHOOK
```

工作流失败时 POST：

```json
{"text":"StockLab 个股质量检查失败，请查看 GitHub Actions 日志"}
```

---

## 7. 重点核查样本

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

## 8. 后续

- 对 `yield_extreme` 增加人工复核标记；
- 对特别分红单独展示；
- 把质量检查结果接入后台页面；
- 连续 3 天同一告警才通知，避免噪声。
