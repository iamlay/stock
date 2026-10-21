# 个股模块 Phase 3 实施报告

> 日期：2026-10-20
> 范围：前端列表/详情/自选/管理页、个股自选 API
> 结论：**Phase 3 完成，个股模块前后端闭环。**

---

## 1. 前端页面

### `/stocks` 高股息列表

- 搜索代码/名称；
- 行业筛选；
- 最低股息率；
- 排序：TTM / 年度 / 市值 / 涨跌幅 / PE；
- 升降序；
- 包含 ST 开关；
- 分页，每页 20；
- 表格列：

```text
代码/名称 | 行业 | 最新价 | 涨跌 | 股息率TTM | 年度股息率 | 市值 | PE | 最近除息
```

### `/stocks/[code]` 个股详情

- 最新价、涨跌、市值、PE/PB；
- TTM 股息率、年度股息率；
- 完整三级行业；
- 最近 100 条分红；
- 特别分红标记；
- 加入/移出自选；
- 数据口径与免责声明。

### `/admin/stocks` 个股管理

- 管理员权限校验；
- 搜索；
- 启用/停用；
- 手动同步；
- 分页。

### 导航

新增「高股息」入口，位于 ETF 数据之后。

---

## 2. 个股自选 API

```text
GET    /api/v1/stock-watchlist
POST   /api/v1/stock-watchlist   {"code":"600519"}
DELETE /api/v1/stock-watchlist/{code}
```

规则：

- 需要登录；
- 只能添加已入库且未停用的个股；
- 重复添加返回 `saved=false`；
- 删除不存在返回 `removed=false`；
- 自选页同时展示 ETF 和个股。

---

## 3. 前端文件

| 文件 | 说明 |
|---|---|
| `app/(app)/stocks/page.tsx` | 列表、筛选、排序、分页 |
| `app/(app)/stocks/[code]/page.tsx` | 详情、分红、自选 |
| `app/(app)/admin/stocks/page.tsx` | 管理 |
| `components/stock-watchlist-button.tsx` | 自选按钮 |
| `lib/stocks.ts` | 个股类型与服务端请求 |
| `lib/auth.ts` | 个股自选、管理端请求 |
| `app/(app)/watchlist/page.tsx` | 增加自选个股区块 |

---

## 4. 验证

```text
next typecheck   ✅ 0 error
next build       ✅ 通过
pytest apps/api  ✅ 98 passed
ruff check       ✅ 0 issue
```

本地页面验证：

```text
/stocks        ✅ 200，列表出现格力电器
/stocks/000651 ✅ 200，出现分红历史
```

---

## 5. 已知限制

- 只能添加已入库的 500 只，不能添加任意代码；
- 行业筛选只对已补行业的股票生效；
- 管理端手动同步是同步请求，可能 2–5 秒；
- 生产尚未灌入个股数据。

> 2026-10-21 更新：已支持详情 K 线和任意 6 位 A 股代码自动补数据，见下一节。

---

## 6. 生产每日更新

- `etl.yml` 每天 18:30 追加执行 `stock-daily`；
- 只更新已入库股票的价格、市值、PE/PB，并重算股息率；
- 不新增股票、不拉分红，避免拖慢每日任务；
- 分红由 `stock-dividends.yml` 每周一 19:00 刷新；
- 行业由 `stock-seed` 或 `stock-industry` 手动/季度刷新。

## 7. 后续增强

### 个股 K 线

- 详情 API 返回最近 250 天 `bars`；
- 首次加入自选或后台手动同步时，用腾讯日线缓存到 `market_daily`；
- 详情页展示收盘价曲线；
- 没同步过时显示“暂无 K 线”。

### 任意代码自动补数据

- `POST /stock-watchlist` 支持任意 6 位 A 股代码；
- 未入库时调用 `sync_stock_quote`：
  - 腾讯最新价；
  - Eastmoney 行业；
  - 腾讯 250 天日线；
  - Eastmoney 分红；
  - 重算股息率；
- 同步成功后加入自选。

## 8. 下一步

1. 生产部署：
   - API 迁移 `5f4740869b51`；
   - 执行 `stock-pilot` 和 `stock-industry`；
2. 扩到全市场 5,000 只；
3. 个股 K 线按需拉取；
4. 用户添加任意代码时自动补数据；
5. 自选页支持排序和批量操作。
