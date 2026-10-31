# 持仓详情 · 交易明细交付

日期：2026-10-31。状态：本地实现、测试与构建通过；生产待验收。

## 已交付

`/portfolio/[code]` 持仓详情按原型改为模块入口：

```text
交易明细      + 添加
分红记录      查看 / 添加
历史分红回溯  待开发
编辑持仓
分红档案
删除持仓      待开发
```

交易明细不再直接铺在详情页，点击进入：

```text
/portfolio/{code}/transactions
```

交易明细页：

- 按日期倒序展示；
- 显示交易类型、日期、数量、价格、费用、成本或收入；
- 支持买入、卖出、送股、分红复投、已有持仓快照、修正、撤销；
- 点击「编辑」进入更正；
- 点击「删除」生成冲正凭据，不删除原记录；
- 底部「+ 添加交易」进入录入页。

录入页顶部用 Tab 切换：

```text
买入 | 卖出 | 送股 | 分红复投
```

持仓详情页不再直接放买入、卖出、送股、分红复投按钮，避免绕过交易明细页。

## 新增交易类型
```text
bonus     送股
reinvest  分红复投
```

口径：

```text
送股：数量增加，总成本不变，平均成本摊薄
分红复投：数量增加，不追加投入，总成本不变
```

两者不填写成交价，不产生交易费用。

## 持仓详情汇总
详情页新增：

```text
累计已获分红
分红回本进度
净投入
已收回分红
剩余待回收
按当前年度分红参考预计回本
```

累计分红来自 V2-53 有效到账记录（净额）；回本进度按“摊薄成本”口径计算，不等于累计买入金额。

## 分红记录页

详情页「分红记录」进入：

```text
/portfolio/{code}/dividends
```

展示：

- 累计已获分红；
- 每笔到账日期、数量、每股派息、税额、实际到账；
- 编辑记录；
- 撤销记录；
- `+ 添加分红`。

添加页：

```text
/portfolio/{code}/dividends/add
```

编辑页：

```text
/portfolio/{code}/dividends/{receiptId}/edit
```

修改接口：

```text
PATCH /api/v1/portfolio/accounts/{account_id}/receipts/{receipt_id}
```

已撤销记录不能修改，只能重新添加。

### 按公告派息日自动登记

每日任务：

```bash
python -m app.cli portfolio-receipts
```

规则：

- 正式实施应收；
- 派息日 <= 今天；
- 尚无有效到账记录；
- 账户未归档且已确认隐私说明；
- 自动生成一条 `source=automatic` 的到账记录；
- 金额按公告应收，税额默认 0；
- 可在分红记录中编辑并补税。

自动记录展示“自动”标签，不会重复生成；撤销后不会自动重新生成。

字段：

```text
入账日期
持仓数量
每股派息
红利税（选填）
实际到账金额（自动计算）
备注（选填）
```

实际到账：

```text
数量 × 每股派息 - 红利税
```

红利税说明弹窗包含 A 股差异化税率、除息不扣/卖出补税、长期持有填 0 的提示。

实收记录新增：

```text
quantity
cash_per_share
```

迁移：

```text
d1a6b9e3f472_dividend_receipt_quantity
```

## 迁移

```text
c9e4a1d7f250_bonus_reinvest
d1a6b9e3f472_dividend_receipt_quantity
e2b7c4a9d183_dividend_receipt_source
```

更新 `portfolio_entries` 的 kind 约束。

## 验证

```text
pytest apps/api -q   ✅ 388 passed, 25 skipped
ruff check           ✅ 0 issue
next typecheck       ✅
next build           ✅
```

## 未做

- 交易列表按类型/日期筛选、分页、批量更正；
- 分红记录独立页；
- 历史回溯独立页；
- 删除持仓；
- Excel/CSV 导入导出。
