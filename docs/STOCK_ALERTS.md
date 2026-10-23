# 自选涨跌 / 除息 / 网格提醒

> 对应 V2-21、V2-30
> 更新：2026-10-23

---

## 1. 规则

### 涨跌提醒

对用户自选中的股票和 ETF：

```text
abs(当日涨跌幅) >= 用户阈值
```

默认阈值 5%，可设置 1–20%。

### 除息提醒

对自选股票：

```text
今天 < 除息日 <= 今天 + 3 天
```

生成一条“将于 X 月 X 日除息”的提醒。

### 网格提醒

对自选股票：

```text
前一日收盘价 > 目标价 >= 当日收盘价
```

即价格**首次跌破**用户设置的股息网格目标价时提醒。

目标价：

```text
近 12 个月每股现金 / 目标股息率
```

默认目标 5%，可选 4% / 4.5% / 5% / 5.5% / 6%。

只在“跌破”当天提醒，不会每天重复。

---

## 2. 数据

### 用户设置

```text
users.alert_price_pct   默认 5%
users.alert_dividend   默认 true
users.alert_email      默认 true
users.alert_grid       默认 true
users.alert_grid_yield 默认 5%
```

### 站内提醒

```text
user_notifications
```

字段：

```text
user_id, type, code, title, body, link,
dedupe_key, read_at, created_at
```

`dedupe_key` 保证同一标的同一触发日只提醒一次。

网格提醒使用：

```text
grid:{trade_date}:{code}:{target_yield}
```

---

## 3. 接口

```text
GET   /api/v1/notifications
GET   /api/v1/notifications/unread-count
GET   /api/v1/notifications/settings
PATCH /api/v1/notifications/settings
POST  /api/v1/notifications/{id}/read
POST  /api/v1/notifications/read-all
```

页面：

```text
/notifications
```

导航新增「提醒」。

---

## 4. 执行

命令：

```bash
python -m app.cli stock-alerts
```

### 推荐：GitHub Actions

```text
Actions → Stock Alerts → Run workflow
```

只生成提醒，不刷新行情。

### 日常：ETL

`etl.yml` 每天 18:30 在个股更新后执行：

```text
Watchlist alerts
python -m app.cli stock-alerts
```

### Railway

在 API 服务容器内执行：

```bash
python -m app.cli stock-alerts
```

Railway 容器内有邮件环境变量，可以发送邮件；GitHub Actions 通常只生成站内提醒。

---

## 5. 邮件

- 只有已验证邮箱、开启邮件提醒、配置了邮件服务才发送；
- 每个用户每次运行最多一封汇总邮件；
- GitHub Actions 没有邮件环境变量时，只生成站内提醒；
- 要发邮件，可在 Railway 服务内运行该命令，或给 Actions 配置邮件 Secret。

---

## 6. 限制

- 只做日频，不做盘中触发；
- 涨跌提醒按当日收盘涨跌幅；
- 除息提醒只覆盖未来 3 天；
- 同一标的同一天只提醒一次；
- 邮件失败不会影响站内提醒。

---

## 7. 验收

- [ ] 自选股票涨跌超过阈值，`/notifications` 出现提醒；
- [ ] 同一标的同一天不重复；
- [ ] 除息日前 3 天出现提醒；
- [ ] 可修改阈值、关闭除息/邮件；
- [ ] 未读数量正确；
- [ ] 标记已读/全部已读正常；
- [ ] 邮件配置后可收到汇总。
