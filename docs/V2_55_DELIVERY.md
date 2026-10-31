# V2-55 收息首页与分红日历交付

日期：2026-10-31。状态：本地实现、测试与构建通过；生产及真实用户样本待验收。

## 已交付

### 收息首页

路由：

```text
/income
```

包含：

- 当年已到账；
- 当年正式待收；
- 预案参考；
- 全部待收；
- 下笔预计到账；
- 月度现金流。

### 分红日历

同页包含月度日历：

```text
登记日
除息日
派息日
实际到账
```

点击日期查看当天事件。日期未知或缺少计算依据的记录进入“日期未知 / 待核对”区域，不伪造日期。

### 数据分层

```text
已收：实际到账净额，按到账日期
正式待收：已实施、有登记日/派息日的应收余额
预案：股东大会通过/董事会预案，仅作参考
```

月度柱状图分别展示已收、待收、预案，不把预案计入实际收入。

### 导航

- 顶部导航新增“收息”；
- `/portfolio` 增加“收息账本”入口；
- `/portfolio/income` 增加“收息首页”入口；
- `/income` 私人页继续排除第三方统计。

## API

```text
GET /api/v1/portfolio/accounts/{account_id}/income/home?year=2026
```

返回：

```text
summary
monthly
calendar
unknown
events
entitlements
```

全部为本人账户数据，沿用私人 API 的 no-store、鉴权与错误脱敏。

## 明确未做

- CSV 导入导出（V2-54）；
- 自动应收重算任务（V2-56）；
- 未来十二个月预测（V2-57）；
- 分红质量与压力测试（V2-58–60）；
- 分红提醒（V2-61）；
- 独立 `/income/calendar`、`/income/receipts` 二级页；
- 多账户、ETF、港美股、公司行动；
- 与真实券商样本的逐笔验收。

## 验证

```text
pytest apps/api -q   ✅ 387 passed, 25 skipped
ruff check           ✅ 0 issue
next typecheck       ✅
next build           ✅
```

本地临时 PostgreSQL/浏览器依赖测试仍按环境跳过。
