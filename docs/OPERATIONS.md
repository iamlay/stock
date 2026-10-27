# StockLab 运维操作手册

> 面向日常维护：部署、数据任务、备份、安全检查、故障排查。
> 更新：2026-10-21
> 配套文档：[部署手册](DEPLOYMENT.md)、[备份与安全](BACKUP_SECURITY.md)、[ETF 100 只](ETF_100.md)、[个股质量](STOCK_QUALITY_REPORT.md)

---

## 1. 服务清单

| 服务 | 地址/位置 | 说明 |
|---|---|---|
| Web | `https://stock.iamlay.com` | Next.js，Vercel |
| API | `https://stock-production-c535.up.railway.app` | FastAPI，Railway API |
| PostgreSQL | Railway Postgres | 生产数据库 |
| 5 分钟 Cron | Railway `stocklab-cron` | `python -m etl.cli cron` |
| ETL | GitHub Actions `ETL` | 每天 18:30 |
| 备份 | GitHub Actions `DB Backup` | 每天 03:00 |
| 质量检查 | GitHub Actions `Stock Quality` | 每周一 20:00 |
| 可用性监控 | GitHub Actions `Uptime Monitor` | 每小时 |

---

## 2. 环境变量

### API（Railway）

| 变量 | 必填 | 说明 |
|---|---|---|
| `STOCKLAB_DATABASE_URL` | ✅ | `${{Postgres.DATABASE_URL}}` 或公网 URL |
| `STOCKLAB_ENV` | ✅ | `production` |
| `STOCKLAB_AUTH_DEV_MODE` | ✅ | 生产必须 `false` |
| `STOCKLAB_JWT_SECRET` | ✅ | ≥32 字节随机值 |
| `STOCKLAB_OTP_SECRET` | ✅ | ≥32 字节随机值 |
| `STOCKLAB_FRONTEND_URL` | ✅ | `https://stock.iamlay.com` |
| `STOCKLAB_CORS_ORIGINS` | ✅ | 正式域名，逗号分隔 |
| `STOCKLAB_EMAIL_PROVIDER` | ✅ | `resend` / `brevo` / `smtp` |
| `STOCKLAB_RESEND_API_KEY` / `STOCKLAB_BREVO_API_KEY` | 二选一 | 邮件服务 |
| `STOCKLAB_EMAIL_FROM` | ✅ | 已验证发件地址 |

### Web（Vercel）

| 变量 | 说明 |
|---|---|
| `API_BASE_URL` | 服务端组件用，必须指向 API |
| `NEXT_PUBLIC_API_BASE_URL` | 浏览器用，必须指向 API |
| `NEXT_TELEMETRY_DISABLED` | 可选 `1` |

> `API_BASE_URL` 和 `NEXT_PUBLIC_API_BASE_URL` 都不带末尾 `/`。
> Web 部署在 Vercel，Railway 只跑 API、PostgreSQL 和 Cron。

### GitHub Secrets

| Secret | 用途 |
|---|---|
| `STOCKLAB_DATABASE_URL` | Actions 连生产库 |
| `BACKUP_ENCRYPTION_KEY` | 备份加密/解密 |
| `STOCKLAB_ALERT_WEBHOOK` | 可选，质量检查失败通知 |

---

## 3. 首次部署

### 3.1 创建 Railway 项目

1. New Project → Deploy from GitHub → `iamlay/stock`；
2. 添加 PostgreSQL；
3. 创建 API 服务：
   - Builder：Dockerfile
   - Dockerfile Path：`apps/api/Dockerfile`
   - 变量：见第 2 节
4. 创建 Web 服务：
   - Builder：Railpack
   - Root Directory：仓库根目录
   - Build Command：`pnpm --filter @stocklab/web build`
   - Start Command：`pnpm --filter @stocklab/web start`
   - 目标端口：`3000`
   - 变量：`API_BASE_URL`、`NEXT_PUBLIC_API_BASE_URL`
5. 创建 cron 服务：
   - Dockerfile：`apps/api/Dockerfile`
   - Start Command：`python -m etl.cli cron`
   - Cron：`*/5 1-7 * * 1-5`
   - 变量：`STOCKLAB_DATABASE_URL`

### 3.2 初始化数据

```bash
python -m etl.cli seed
python -m etl.cli sync-all --start 2016-01-01 --delay 0.2
python -m etl.cli sync-shares
python -m etl.cli sync-valuation
python -m etl.cli stock-pilot --limit 500 --dividend-limit 500
python -m etl.cli stock-industry --limit 500
```

### 3.3 创建管理员

```bash
python -m app.cli create-admin --email admin@example.com
```

---

## 4. 日常发布流程

### 4.1 API 发布

1. 合并到 `main`；
2. Railway API 检测到新 commit 自动部署；
3. 容器启动时自动执行：

```bash
alembic upgrade head
uvicorn app.main:app
```

4. 检查：

```bash
curl https://stock-production-c535.up.railway.app/healthz
```

### 4.2 Web 发布

1. 合并到 `main`；
2. Vercel 自动重新构建；
3. 检查：

```bash
curl -I https://stock.iamlay.com
```

4. 如果页面还是旧数据，强制刷新或检查 Vercel 的 `API_BASE_URL`。

### 4.3 发布后检查清单

- [ ] `/healthz` 200
- [ ] `/dashboard` 显示真实数据
- [ ] `/etf` 可打开
- [ ] `/stocks` 可打开
- [ ] 登录/自选可用
- [ ] 新迁移无报错

---

## 5. 数据库迁移

### 查看当前版本

```bash
alembic -c apps/api/alembic.ini current
```

### 本地生成迁移

```bash
cd apps/api
alembic revision --autogenerate -m "change"
```

### 生产执行

API 容器启动自动执行，无需手动。

### 回滚

```bash
alembic -c apps/api/alembic.ini downgrade -1
```

> 生产回滚前先备份；涉及删列/删表的迁移要单独评审。

---

## 6. 定时任务

| 工作流 | 时间（北京） | 命令 | 说明 |
|---|---|---|---|
| `ETL` | 工作日 18:30 | `etl.cli daily` + `etl.cli stock-daily` + `app.cli stock-alerts` | ETF/个股/提醒 |
| `Stock Dividends` | 周一 19:00 | `etl.cli stock-dividends-bulk` | 分红与股息率 |
| `Stock Quality` | 周一 20:00 | `etl.cli stock-metrics` + `stock-quality --write` | 质量检查 |
| `Stock Alerts` | 手动 | `app.cli stock-alerts` | 只跑提醒 |
| `DB Backup` | 每天 03:00 | `pg_dump` + 加密 | 备份 |
| `Stock Bars` | 每月 1 日 20:00 | `etl.cli stock-bars --limit 2000` | K 线 |
| `Stock Yield Percentile` | 每月 1 日 22:00 | `stock-yield-percentile --limit 1000` | 10 年分位 |
| `Stock Financials` | 每月 1 日 21:00 | 5 分片并行，增量跳过 | 年报/季报 |
| `Stock Industry Detail` | 每季度首日 20:30 | `stock-industry-detail --limit 500` | 三级行业 |
| `Stock Full Market` | 手动 | 5,000 只初始化 | 首次/扩量 |
| `Stock Industry` | 手动 | 申万一级行业 | 修复行业 |
| `Stock Seed` | 手动 | 500 只灰度 | 首次 |
| `DB Restore Test` | 手动 | 恢复最近备份 | 验证备份 |
| `Uptime Monitor` | 每小时 | API/Web/数据新鲜度 | 可用性告警 |

### Railway 5 分钟 Cron

```text
python -m etl.cli cron
```

做三件事：

1. 刷新 ETF 最新报价；
2. 刷新所有用户自选股最新报价；
3. 标记过期邀请码。

自选股表：

```text
stock_realtime_quotes
```

手动执行：

```bash
python -m etl.cli stock-watchlist-quotes --force
```

---

## 7. 常用数据命令

```bash
# ETF
python -m etl.cli seed
python -m etl.cli sync-all --start 2016-01-01 --delay 0.2
python -m etl.cli sync-shares
python -m etl.cli sync-valuation
python -m etl.cli sync-quotes --force
python -m etl.cli daily

# 个股
python -m etl.cli stock-universe --limit 5000
python -m etl.cli stock-dividends-bulk --days 3650
python -m etl.cli stock-metrics --limit 5000
python -m etl.cli stock-industry --limit 5000 --sina-only --sina-prefix sw_ --overwrite
python -m etl.cli stock-industry-detail --limit 500
python -m etl.cli stock-bars --limit 2000
python -m etl.cli stock-yield-percentile --limit 1000
python -m etl.cli stock-financials --limit 5000

# 手动分片，每片约 1,000 只
python -m etl.cli stock-financials --limit 5000 --shard-count 5 --shard-index 0
python -m etl.cli stock-financials --limit 5000 --shard-count 5 --shard-index 1

# 强制忽略增量跳过
python -m etl.cli stock-financials --limit 5000 --force
python -m etl.cli stock-quality --limit 5000 --write
python -m etl.cli stock-status
python -m app.cli stock-alerts

# 运维
python -m app.cli security-check
python -m app.cli rotate-tokens
python -m etl.cli status
python -m etl.cli quality --limit 20
```

财务增量规则：

```text
按当前日期推算最新应披露报告期
已有该报告期的股票直接跳过
未披露新报告的股票仍会重试
```

报告期推算：

```text
10-31 后：当年三季报
08-31 后：当年中报
04-30 后：当年一季报
其他时间：上一年年报
```

---

## 8. 备份与恢复

### 备份

```text
Actions → DB Backup → Run workflow
```

产物：

```text
stocklab-db-<run_id>.zip
  stocklab-YYYY-MM-DD.dump.enc
```

### 恢复演练

```text
Actions → DB Restore Test → Run workflow
run_id: 上一步 DB Backup 的 run id
```

工作流会启动临时 PostgreSQL 18，恢复并输出行数。

### 手动恢复

```bash
STOCKLAB_DATABASE_URL='postgresql://...' \
BACKUP_ENCRYPTION_KEY='...' \
bash scripts/restore_backup.sh stocklab-2026-10-21.dump.enc
```

> 生产恢复前必须再次备份当前库。

---

## 9. 安全检查

```bash
python -m app.cli security-check
```

目标：0 个 FAIL。

### 密钥轮换顺序

1. JWT / OTP；
2. 重新部署 API；
3. 旧登录态失效；
4. 数据库密码；
5. 邮件 Key；
6. 再跑 `security-check`。

### DB 公网

关闭 Public Networking 前必须先确认：

- GitHub Actions 不再直连公网 DB；
- ETL/备份/质量任务已迁到 Railway 内网。

否则所有 Actions 会失败。

---

## 10. 监控与健康检查

### 自动监控

`Uptime Monitor` 每小时检查：

- API `/healthz`；
- Web 首页；
- `/api/v1/data/status`；
- 数据最新日期不超过 10 天；
- 质量检查无 fail；
- 最近数据任务不是 failed。

失败时 GitHub Actions 会失败；配置 `STOCKLAB_ALERT_WEBHOOK` 可额外发 Slack/飞书通知。

### API

```bash
curl https://stock-production-c535.up.railway.app/healthz
```

返回：

```json
{"status":"ok","service":"stocklab-api"}
```

### 数据

```bash
curl https://stock-production-c535.up.railway.app/api/v1/data/status
```

关注：

- `latest_trade_date`
- `daily_bars`
- `failed_quality_checks`
- `last_job.status`

### 页面

- `/dashboard` 是否显示真实数据；
- `/etf` 是否 100 只；
- `/stocks` 是否 4,872 只非 ST；
- `/notifications` 是否可打开。

---

## 11. 故障排查

### 页面显示“示例数据”

1. 检查 Web 的 `API_BASE_URL`；
2. 确认 API `/healthz`；
3. 确认 Web 已重新部署；
4. 检查 `NEXT_PUBLIC_API_BASE_URL`。

### API 502 / 启动失败

1. Railway Logs 看迁移错误；
2. 检查 `STOCKLAB_DATABASE_URL`；
3. 检查是否引用了未解析的 `${{...}}`；
4. 检查 Dockerfile 路径。

### 数据没更新

1. Actions 最近一次 ETL 是否成功；
2. `/api/v1/data/status` 的 `latest_trade_date`；
3. 检查 `stock-daily` 日志；
4. 检查交易日/停牌。

### GitHub Actions 连接数据库失败

- `STOCKLAB_DATABASE_URL` 是否过期；
- Railway DB 是否开启 Public Networking；
- 密码是否轮换过；
- 代理是否临时重置（重试）。

### pg_dump 版本不匹配

```text
server 18.x / pg_dump 16.x
```

必须用：

```text
/usr/lib/postgresql/18/bin/pg_dump
```

### 全市场任务卡住

- 是否用旧代码逐行 `session.get`；
- 是否先跑 `stock-universe` 再跑分红；
- 是否多个 Actions 同时抢数据库连接。

### 质量检查 fail

1. 看 `stock-quality.json`；
2. 看 `fail` 项：价格缺失、股息率 >30%、重复分红；
3. 修复数据后重跑；
4. 配置 `STOCKLAB_ALERT_WEBHOOK` 接收通知。

### 页面缓存旧数据

- 个股页已 `force-dynamic` / `no-store`；
- 其他页面检查 ISR/revalidate；
- 强制刷新；
- 重新部署。

---

## 12. 回滚

### 代码回滚

```bash
git revert <commit>
git push origin main
```

Railway 自动重新部署。

### 数据库回滚

```bash
alembic -c apps/api/alembic.ini downgrade -1
```

> 只在确认迁移可逆时执行。

### 数据回滚

用最近一次加密备份恢复：

```text
DB Restore Test 先验证
→ 再对生产执行 restore
```

---

## 13. 变更检查清单

每次上线前：

- [ ] CI 绿色
- [ ] `pytest` / `ruff` / `next build`
- [ ] 迁移已生成
- [ ] API/Web 已部署
- [ ] 数据任务已跑
- [ ] `/healthz` 正常
- [ ] 关键页面正常
- [ ] 备份可用
- [ ] 有回滚方案

---

## 14. 当前待上线（2026-10-21）

以下 commit 的功能需要部署后验收：

```text
85cb387  分红标记/可持续性/质量告警
41b39c7  自选提醒
79d5129  ETF 100 只
```

迁移：

```text
797e0ddfc988  stock dividend flags
41b39c7d5a9a  stock alerts
```

ETF 100 只启用后还要跑：

```bash
python -m etl.cli seed
python -m etl.cli sync-all --start 2016-01-01 --delay 0.2
python -m etl.cli sync-shares
python -m etl.cli sync-valuation
```
