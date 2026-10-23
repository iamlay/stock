# 会员权限边界

> 日期：2026-10-23
> 对应 V2-10
> 状态：界面门禁 + 关键接口限制已上线

---

## 1. 权益表

| 功能 | 游客 | 免费用户 | 会员 |
|---|---|---|---|
| ETF / 个股列表、基础详情 | ✅ | ✅ | ✅ |
| 今日市场、行业图 | ✅ | ✅ | ✅ |
| 个股搜索 | ✅ | ✅ | ✅ |
| 个股 / ETF 自选 | ❌ | 最多 10 个 | 不限 |
| 涨跌提醒 | ❌ | ✅ | ✅ |
| 除息提醒 | ❌ | ✅ | ✅ |
| 网格提醒 | ❌ | ❌ | ✅ |
| 股息网格 | ❌ | ❌ | ✅ |
| 布林追踪 | ❌ | ❌ | ✅ |
| 财务追踪 | ❌ | ❌ | ✅ |
| 回测历史 / 导出 | ❌ | ❌ | ✅ |
| 回测次数 | 每日限额 | 每日限额 | 不限 |

免费自选限制是**股票 + ETF 合计** 10 个。

---

## 2. 实现

### 2.1 服务端限制

`apps/api/app/services/entitlements.py`：

```text
FREE_WATCHLIST_LIMIT = 10
ensure_watchlist_slot()
require_member()
```

已接入：

- `POST /api/v1/watchlist`：免费用户超过 10 个返回 403；
- `POST /api/v1/stock-watchlist`：同样限制；
- `PATCH /api/v1/notifications/settings`：
  - 免费用户开启网格提醒返回 403；
  - 免费用户修改网格目标返回 403；
- `run_stock_alerts`：只有会员才生成网格提醒。

### 2.2 界面门禁

新增：

```text
apps/web/components/member-gate.tsx
```

覆盖：

```text
/stocks/grid        股息网格
/stocks/bollinger   布林
/stocks/financial   财务
/stocks/{code}?tab=grid
/stocks/{code}?tab=bollinger
/stocks/{code}?tab=financial
```

非会员看到升级卡片，不显示具体数据。

### 2.3 登录状态

`MemberGate` 使用 `/api/v1/auth/me` 的：

```text
is_member
plan
plan_expires_at
```

会员过期后自动回退到免费。

---

## 3. 定价页

`/pricing` 新增权限边界表：

```text
功能 | 免费 | 会员
```

同时更新会员权益文案：

- 股息网格 / 布林 / 财务；
- 自选不限数量；
- 网格提醒；
- 回测历史与导出。

---

## 4. 验收

- [ ] 免费用户第 11 个自选返回 403；
- [ ] 会员可无限添加自选；
- [ ] 免费用户打开 `/stocks/grid` 看到升级卡片；
- [ ] 免费用户打开布林/财务看到升级卡片；
- [ ] 会员可正常查看三个高级页面；
- [ ] 免费用户请求 `/stocks/grid` 返回 403；
- [ ] 匿名请求 `/stocks/bollinger` 返回 401；
- [ ] 免费用户请求 `/stocks/financials` 返回 403；
- [ ] 会员 Cookie 请求高级接口返回 200；
- [ ] 免费用户开启网格提醒返回 403；
- [ ] 会员开启网格提醒成功；
- [ ] 会员到期后 advanced 页面自动锁定；
- [ ] `/pricing` 显示权限边界。

---

## 5. Cookie 硬门禁

登录后：

```text
API 返回 access_token
→ 前端 localStorage 保存
→ POST /api/session 写入 HttpOnly Cookie：stocklab_token
```

Cookie 属性：

```text
HttpOnly
Secure（生产）
SameSite=Lax
Path=/
Max-Age=30 天
```

Web 服务端页面：

```text
cookies() 读取 stocklab_token
→ 作为 Authorization: Bearer 转发给 API
```

API 认证同时接受：

```text
Authorization: Bearer <token>
Cookie: stocklab_token=<token>
```

### 已强制返回 401 / 403 的接口

```text
GET /api/v1/stocks/grid         未登录 401，免费 403
GET /api/v1/stocks/bollinger    未登录 401，免费 403
GET /api/v1/stocks/financials   未登录 401，免费 403
GET /api/v1/stocks/{code}       财务字段仅会员返回
```

会员到期后：

```text
Cookie 仍在
→ API 解析用户
→ is_member=false
→ 403
```

### 网格 API

```text
GET /api/v1/stocks/grid
```

已改为会员专享：

- 匿名 401；
- 免费 403；
- 会员 200；
- `/stocks/grid` 页面通过 Cookie 转发请求，不再使用公开个股列表计算。

---

## 6. 配置

免费自选上限：

```python
FREE_WATCHLIST_LIMIT = 10
```

如需调整，只改：

```text
apps/api/app/services/entitlements.py
```
