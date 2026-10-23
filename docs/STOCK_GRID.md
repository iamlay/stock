# 股息网格与个股详情 Tab

> 日期：2026-10-23
> 对应：V2-30
> 状态：网格、布林、财务均已上线

---

## 1. 页面结构

个股模块拆成 4 个列表：

```text
/stocks             高股息
/stocks/grid        股息网格
/stocks/bollinger   布林（占位）
/stocks/financial   财务
```

个股详情拆成 5 个 Tab：

```text
/stocks/600519?tab=overview
/stocks/600519?tab=dividend
/stocks/600519?tab=grid
/stocks/600519?tab=bollinger
/stocks/600519?tab=financial
```

---

## 2. 网格计算

输入：

```text
最新价
TTM 股息率
```

先还原近 12 个月每股现金分红：

```text
annual_cash = price × ttm_yield / 100
```

目标价：

```text
target_price = annual_cash / target_yield
```

档位：

```text
4.0% / 4.5% / 5.0% / 5.5% / 6.0%
```

距现价：

```text
( target_price / price - 1 ) × 100%
```

### 示例

```text
现价 42.28
TTM 股息率 4.77%
annual_cash = 42.28 × 4.77% = 2.016
5% 目标价 = 2.016 / 5% = 40.32
```

---

## 3. 列表页

`/stocks/grid` 支持：

- 按 TTM 股息率排序；
- 搜索代码/名称；
- 行业过滤；
- 最低股息率；
- 分页。

展示：

```text
代码 / 名称
行业
现价
TTM 股息率
4% / 4.5% / 5% / 5.5% / 6% 目标价
距现价
```

绿色表示当前股息率已经达到该档。

---

## 4. 详情页

`tab=grid` 显示单只股票的网格表：

```text
目标股息率
目标价
距现价
对应年现金
```

`tab=overview` 显示价格走势。

`tab=dividend` 显示分红历史与财年汇总。

`tab=bollinger` / `tab=financial` 为下一阶段占位。

---

## 5. 限制

- 只覆盖有 TTM 现金分红的股票；
- 使用近 12 个月已除息分红，不预测未来；
- 特别分红会抬高目标价；
- 分红下降后网格会失真；
- 不是实时行情；
- 不构成投资建议。

---

## 6. 验收

- [ ] `/stocks` 顶部出现 4 个 Tab；
- [ ] `/stocks/grid` 可搜索、分页；
- [ ] 表格有 4%–6% 五档价格；
- [ ] 个股详情出现 5 个 Tab；
- [ ] `tab=grid` 显示目标价；
- [ ] 手机端显示网格卡片；
- [ ] 切换 Tab 不丢股票代码。

---

## 7. 下一阶段

```text
1. 布林：已完成 /stocks/bollinger
2. 财务：已完成 /stocks/financial
3. 网格提醒：已完成，首次跌破目标价触发站内提醒
```

## 8. 网格提醒

用户设置：

```text
alert_grid       默认开启
alert_grid_yield 默认 5%
```

触发条件：

```text
前一日收盘 > 目标价 >= 当日收盘
```

目标价按近 12 个月现金分红 / 目标股息率计算。

触发后生成：

```text
type = grid
link = /stocks/{code}?tab=grid
dedupe_key = grid:{trade_date}:{code}:{yield}
```

只在跌破当天提醒一次，不重复每日提醒。


## 8. 布林

已新增：

```text
GET /api/v1/stocks/bollinger
/stocks/bollinger
/stocks/{code}?tab=bollinger
```

规则：

- 20 周期均线 ± 2 倍标准差；
- 日线直接用日 K；
- 周线按自然周聚合；
- 月线按自然月聚合；
- 日/周/月各需 20 个周期；
- 评级：回踩 / 偏热 / 高位 / 观望 / 数据不足。

K 线缓存从 250 天扩展到 600 天，详情 API 返回 600 根，月线才有足够数据。
K 线覆盖已扩展到 2,000 只。

## 9. 财务

已新增：

```text
GET /api/v1/stocks/financials
/stocks/financial
/stocks/{code}?tab=financial
```

数据表：

```text
stock_financials
```

字段：

```text
code, report_date, period
revenue, net_profit
revenue_yoy, net_profit_yoy
roe, operating_cash_flow_per_share
operating_cash_flow, gross_margin, net_margin
disclosure_date
```

同步：

```bash
python -m etl.cli stock-financials --limit 1000 --delay 0.2
```

当前覆盖高股息前 1,000 只；默认每月 1 日更新，也可手动触发 GitHub Actions。

财务质量字段：

- 营收同比；
- 归母净利同比；
- 加权 ROE；
- 每股经营现金流；
- 经营现金流总额；
- 毛利率；
- 净利率。


