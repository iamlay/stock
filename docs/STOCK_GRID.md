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

> 月布林为空时，先确认 `stock_bars` 是否只有 250 天。`stock-bars` 会跳过已有 600 天以上的股票，旧数据不足 600 天会自动重拉。

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
total_assets, total_liabilities, debt_asset_ratio, roa
disclosure_date
```

同步：

```bash
python -m etl.cli stock-financials --limit 5000 --delay 0.2
```

当前覆盖全市场 5,000 只；默认每月 1 日更新，也可手动触发 GitHub Actions。

财务质量字段：

- 营收同比；
- 归母净利同比；
- 加权 ROE；
- 每股经营现金流；
- 经营现金流总额；
- 毛利率；
- 净利率。

## 10. 10 年股息率分位

新增字段：

```text
stock_metrics.yield_percentile
```

计算：

```text
每周取最后一个交易日
→ 近 12 个月已除息现金 / 收盘价
→ 得到 10 年周频股息率序列
→ 当前 TTM 股息率在序列中的百分位
```

分位标签：

```text
>= 80%  10年高位
20-80%  10年中位
<= 20%  10年低位
```

执行：

```bash
# 先补 10 年 K 线（建议先 1,000 只）
python -m etl.cli stock-bars --limit 1000 --days 3650

# 再算分位
python -m etl.cli stock-yield-percentile --limit 1000 --days 3650
```

说明：

- 分位只对已补足 10 年 K 线且有分红记录的股票生效；
- 不足 52 周历史的股票会跳过；
- 与参考图的 RLY 口径仍有差异：当前使用已除息分红，不是已宣告未除息。

## 11. RLY 已宣告分红

新增字段：

```text
stock_metrics.dividend_yield_ly
```

严格 RLY 口径：

```text
最新年报现金分红
+ 最新中报/季报现金分红（报告期晚于最新年报）
/ 当前价
```

公告过滤：

```text
公告日或除息日 <= 今天
公告金额 > 0
年报按报告期 12-31
中报/季报按 3-31 / 6-30 / 9-30
```

新增公告字段：

```text
stock_dividends.notice_date
stock_dividends.report_date
stock_dividends.progress
stock_dividends.ex_date 允许为空
```

同步：

```bash
python -m etl.cli stock-dividends-bulk --days 3650
python -m etl.cli stock-metrics --limit 5000
```

说明：

- 未公布金额的“预披露”记录不会进入 RLY；
- 分红金额仍按每股现金，未额外处理送转复权；
- 与 TTM 的差异来自“已宣告/未来除息”与“已除息”的口径差异；
- 页面 `/watchlist` 显示 `RLY`。

## 12. 自选排序与筛选

自选个股支持：

```text
按 TTM 股息率
按 RLY
按 10 年分位
按 BOLL 低位
按市值
按名称
```

筛选：

```text
低位共振：周线中下/下轨 且 月线中下/下轨
低估值：10 年股息率分位 >= 80%
```

页面会标记：

```text
低位共振
低估值
```

BOLL 低位排序按周线、月线位置 rank 求和，越低越靠前。

## 13. 筛选条件保存与共振提醒

自选页会把以下条件保存到浏览器：

```text
ETF 排序
个股排序
低位共振
低估值
```

存储键：

```text
stocklab.watchlist.prefs
```

新增用户设置：

```text
users.alert_resonance  默认 true
```

会员满足以下条件时生成站内提醒：

```text
10 年股息率分位 >= 80%
周线 BOLL 位置 = 中下 / 下轨下方
月线 BOLL 位置 = 中下 / 下轨下方
```

提醒：

```text
type = resonance
link = /stocks/{code}?tab=bollinger
dedupe = resonance:{year}-W{week}:{code}
```

每周最多提醒一次，避免长期低位每天重复。

覆盖范围：

```text
10 年股息率分位：前 1,000 只
共振提醒：自选股 + 已计算分位
```

不在前 1,000 的自选股不会触发共振提醒。





