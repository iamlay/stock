# V2-52 / V2-53 应收与实收交付

日期：2026-10-29。状态：本地实现、测试与构建通过；生产部署及真实券商样本待验收。

## 已交付

### V2-52 登记时点应收

- 读取已核对、正式实施、登记日和每股现金完整的 `DividendEvent/Version`。
- 按登记日收盘重放本人有效持仓，计算合资格股数。
- 生成版本化应收：
  - 登记股数；
  - 每股现金；
  - 税前应收；
  - 事件版本和计算版本。
- 只生成正式应收，不把预案、未知日期、未核对历史或公司行动静默计入。
- 登记后卖出不撤销已生成权益；除息后买入不获得旧权益。
- 持仓历史不完整、登记日早于记账起点、历史超卖、送转计划等进入跳过原因，不伪造金额。

### V2-53 实收与核对

- 到账记录支持：
  - 关联应收或独立到账；
  - 实际到账日期；
  - 净额；
  - 税前金额和税额（可只填净额）；
  - 备注；
  - 撤销，保留记录和撤销时间。
- 应收状态自动计算：
  - 待收；
  - 部分到账；
  - 已收齐；
  - 待核对；
  - 已失效。
- 税前/税额校验：税前 = 净额 + 税额；税额不能为负。
- 同一请求编号重复提交幂等；不同内容返回冲突。
- 写入使用账户版本锁、隐私说明确认、归档只读和操作审计。

## API

```text
GET  /api/v1/portfolio/accounts/{account_id}/income
POST /api/v1/portfolio/accounts/{account_id}/income/refresh
POST /api/v1/portfolio/accounts/{account_id}/receipts
POST /api/v1/portfolio/accounts/{account_id}/receipts/{receipt_id}/reverse
```

`refresh` 可重复执行，不重复生成应收。

## 页面

```text
/portfolio
→ 收息账本
```

或直接：

```text
/portfolio/income
```

页面包含：

- 税前应收、已到账净额、待收余额；
- 应收列表；
- 登记到账表单；
- 到账记录和撤销。

## 数据

迁移：

```text
b2d5e7f1a034_portfolio_income
```

新增表：

```text
dividend_entitlements
dividend_receipts
```

## 明确未做

- 分红日历和年度收息汇总页（V2-55）；
- CSV 导入导出（V2-54）；
- 未来十二个月预测（V2-57）；
- 分红质量和压力测试（V2-58–60）；
- 分红提醒（V2-61）；
- ETF、港美股、多币种；
- 送转、拆并股等公司行动自动调整；
- 券商自动同步和 OCR；
- 自动把未核对旧分红转成正式应收。

## 验证

```text
pytest apps/api -q   ✅ 387 passed, 25 skipped
ruff check           ✅ 0 issue
next typecheck       ✅
next build           ✅
alembic heads        ✅ b2d5e7f1a034
```

生产和真实券商样本核对尚未完成，不能标记为上线验收完成。
