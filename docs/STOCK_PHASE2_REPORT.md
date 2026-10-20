# 个股模块 Phase 2 实施报告

> 日期：2026-10-20
> 范围：个股列表 API、详情 API、管理端接口
> 结论：**Phase 2 完成，前端可以开始接。**

---

## 1. 已完成接口

### 列表

```text
GET /api/v1/stocks
  ?sort=dividend_yield_ttm
  &order=desc
  &q=
  &industry=
  &min_yield=
  &include_st=false
  &page=1
  &page_size=20
```

排序字段白名单：

```text
dividend_yield_ttm  默认
dividend_yield_fy
market_cap
change_pct
pe_ttm
```

规则：

- 默认排除 ST；
- 默认排除 `status=excluded`；
- 无价格/无行情的股票不返回；
- 股息率为 `NULL` 时排在最后；
- 分页最大 100。

### 详情

```text
GET /api/v1/stocks/{code}
```

返回：

- 名称、行业、三级行业路径、板块、ST；
- 最新价、涨跌、市值、PE/PB；
- TTM/年度股息率、最近除息日；
- 最近 100 条分红记录。

### 管理端

```text
GET   /api/v1/admin/stocks
PATCH /api/v1/admin/stocks/{code}   {"status":"active|excluded"}
POST  /api/v1/admin/stocks/{code}/sync
```

- 仅 `admin` 可访问；
- 状态变更和手动同步写 `admin_audit_logs`；
- 手动同步复用 `etl.stocks.sync_stock_quote`。

---

## 2. 返回示例

```json
{
  "items": [
    {
      "code": "601398",
      "name": "工商银行",
      "industry": "金融",
      "industry_path": "金融-银行-国有银行",
      "market": "SH",
      "is_st": false,
      "price": 8.58,
      "change_pct": 0.35,
      "market_cap": 30500.0,
      "pe_ttm": 6.1,
      "pb": 0.7,
      "dividend_yield_ttm": 5.2,
      "dividend_yield_fy": 5.2,
      "last_ex_date": "2026-05-13",
      "updated_at": "2026-10-20T10:30:00+00:00"
    }
  ],
  "total": 431,
  "page": 1,
  "page_size": 20,
  "sort": "dividend_yield_ttm",
  "order": "desc"
}
```

---

## 3. 实现细节

| 项 | 说明 |
|---|---|
| 查询 | `instruments` + `stock_profiles` + `stock_metrics` 三表 join |
| 排序 | SQLAlchemy `nulls_last()` |
| 搜索 | 代码/名称 `ilike` |
| 行业 | 精确匹配一级行业 |
| 最低股息率 | `dividend_yield_ttm >= min_yield` |
| 权限 | 管理端 `get_current_admin` |
| 审计 | `AdminAuditLog` |

---

## 4. 测试

新增 `apps/api/tests/test_stocks_api.py`：

- 默认按 TTM 股息率降序；
- 默认排除 ST；
- `include_st=true` 可显示；
- 行业 + 最低股息率筛选；
- 详情返回分红；
- 普通用户访问管理端 403；
- 管理员停用后列表不再返回。

结果：

```text
pytest apps/api -q   ✅ 97 passed
ruff check           ✅ 0 issue
```

---

## 5. 已知限制

- 还没有前端页面；
- 详情暂不返回 K 线（股票日线未入库，Phase 3 按需拉）；
- 行业筛选只对已补行业的股票生效；
- 手动同步是同步请求，可能耗时 2–5 秒；
- 全市场还没扩量，当前 500 只。

---

## 6. 下一步 Phase 3

1. `/stocks` 列表页：
   - 搜索、行业、最低股息率、排除 ST；
   - 排序下拉；
   - 分页；
   - 添加自选。
2. `/stocks/[code]` 详情页：
   - 指标卡片；
   - 分红历史；
   - 价格曲线（按需拉 K 线）；
   - 自选按钮。
3. `/admin/stocks` 管理页；
4. 导航新增「高股息」；
5. 用户自选接口 `stock-watchlist`。
