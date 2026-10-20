# 个股行业补全 Phase 1.5 报告

> 日期：2026-10-20
> 范围：500 只灰度股票的行业补全
> 结论：**500/500 全部补全，0 失败。**

---

## 1. 执行

```bash
python -m etl.cli stock-industry --limit 500 --delay 0.15
```

输出：

```text
stock industry selected=500 sina=315 eastmoney=500 errors=0
```

说明：

- Sina 先覆盖 315 只粗分类；
- Eastmoney F10 最终覆盖 500 只，全部使用三级行业；
- 0 只失败。

---

## 2. 结果

```text
with_industry=500 / 500
```

行业分布前 10：

| 行业 | 数量 |
|---|---|
| 电子设备 | 110 |
| 金融 | 58 |
| 信息技术 | 40 |
| 有色金属 | 36 |
| 医药生物 | 28 |
| 基础化工 | 25 |
| 电气设备 | 25 |
| 公用事业 | 24 |
| 机械设备 | 23 |
| 交通运输 | 22 |

> 分布偏向电子/金融，是因为灰度按市值取前 500，不是全市场行业分布。

样例：

```text
002353  化石能源   化石能源-石油天然气-油田服务
002600  电子设备   电子设备-电子元件-电子元件
002602  互联网     互联网-互联网服务-游戏娱乐
```

---

## 3. 数据模型

`stock_profiles` 已写入：

```text
industry          一级行业（用于筛选）
industry_path     完整三级路径（用于详情）
industry_source   eastmoney / sina
list_date         上市日
```

---

## 4. 命令

```bash
# 补 500 只
python -m etl.cli stock-industry --limit 500

# 只跑 Eastmoney，不用 Sina 预填
python -m etl.cli stock-industry --limit 500 --skip-sina

# 降低请求频率
python -m etl.cli stock-industry --limit 500 --delay 0.3
```

---

## 5. 验证

```text
pytest apps/api -q   ✅ 94 passed
ruff check           ✅ 0 issue
500 只行业           ✅ 500/500
Eastmoney 失败       ✅ 0
```

---

## 6. 已知限制

- Eastmoney F10 是逐只请求，5,000 只全量约 1–2 小时；
- 行业分类会随公司调整，需要季度刷新；
- 行业口径是东财 `EM2016`，不是申万；
- 新上市股票需要补跑 `stock-industry`。

---

## 7. 下一步

1. Phase 2：`/api/v1/stocks` 列表/详情/排序；
2. Phase 3：前端 `/stocks`、`/stocks/[code]`、自选；
3. 全市场扩量时，行业后台分批补，不阻塞排序上线。
