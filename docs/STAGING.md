# StockLab 测试环境（Staging）搭建方案

> 目标：有一套与生产隔离、可随时重置、可跑 E2E 的测试环境。
> 更新：2026-10-22
> 关联：[运维操作手册](OPERATIONS.md)

---

## 1. 原则

测试环境必须满足：

- **数据库隔离**：不能连生产库；
- **密钥隔离**：JWT/OTP/邮件 Key 不与生产共用；
- **域名隔离**：`staging.stock.iamlay.com`；
- **数据可控**：只灌少量 ETF/股票，不复制真实用户；
- **可重置**：坏了可以清库重来；
- **默认不公开**：加访问保护，禁止搜索引擎收录。

不要做：

- ❌ 不要复制生产数据库到 staging（含真实邮箱/手机号）；
- ❌ 不要让 staging 使用生产 JWT/OTP Secret；
- ❌ 不要让 staging 的 ETL 写生产库；
- ❌ 不要把 staging 暴露成公开站点。

---

## 2. 推荐架构

```text
GitHub main       → Railway Production
GitHub staging    → Railway Staging
```

| 环境 | 分支 | 域名 | 数据库 |
|---|---|---|---|
| Production | `main` | `stock.iamlay.com` | 生产 Postgres |
| Staging | `staging` | `staging.stock.iamlay.com` | 独立 Postgres |

推荐**单独建一个 Railway Project**：

```text
stocklab-staging
```

而不是复用生产项目。原因：

- 避免误连生产库；
- 避免误删生产服务；
- 环境变量完全独立；
- 出问题不影响生产。

---

## 3. 创建步骤

### 3.1 建分支

```bash
git checkout main
git pull
git checkout -b staging
git push origin staging
```

以后：

```text
功能分支 → staging → main
```

### 3.2 建 Railway 项目

1. Railway → New Project；
2. Deploy from GitHub → `iamlay/stock`；
3. 添加 PostgreSQL；
4. 创建 API 服务；
5. 创建 Web 服务。

### 3.3 API 服务

| 项 | 值 |
|---|---|
| 分支 | `staging` |
| Builder | Dockerfile |
| Dockerfile Path | `apps/api/Dockerfile` |
| 变量 | 见下表 |

环境变量：

```text
STOCKLAB_ENV=staging
STOCKLAB_DATABASE_URL=${{Postgres.DATABASE_URL}}
STOCKLAB_AUTH_DEV_MODE=true
STOCKLAB_JWT_SECRET=<staging 独立随机值>
STOCKLAB_OTP_SECRET=<staging 独立随机值>
STOCKLAB_FRONTEND_URL=https://staging.stock.iamlay.com
STOCKLAB_CORS_ORIGINS=https://staging.stock.iamlay.com,http://localhost:3000
STOCKLAB_EMAIL_PROVIDER=resend
STOCKLAB_RESEND_API_KEY=<测试 Key>
STOCKLAB_EMAIL_FROM=no-reply@iamlay.com
```

如果不想发真实邮件：

```text
STOCKLAB_AUTH_DEV_MODE=true
```

验证邮件 token 会写入 API 日志，测试时从日志取。

### 3.4 Web 服务

| 项 | 值 |
|---|---|
| 分支 | `staging` |
| Builder | Railpack |
| Build Command | `pnpm --filter @stocklab/web build` |
| Start Command | `pnpm --filter @stocklab/web start` |
| 目标端口 | 3000 |
| 变量 | 见下表 |

```text
API_BASE_URL=https://<staging-api>.up.railway.app
NEXT_PUBLIC_API_BASE_URL=https://<staging-api>.up.railway.app
```

### 3.5 域名

Railway Web → Settings → Networking → Custom Domain：

```text
staging.stock.iamlay.com
```

DNS 添加 CNAME。

### 3.6 不做

- staging 不需要 5 分钟 Cron；
- staging 不需要真实支付；
- staging 不需要生产备份策略；
- staging 不需要公开注册入口。

---

## 4. 初始化测试数据

### 4.1 基础 ETF

不要同步 2016 年至今全量，测试用近一年即可：

```bash
python -m etl.cli seed
python -m etl.cli sync-all --start 2025-01-01 --delay 0.2
python -m etl.cli sync-shares
python -m etl.cli sync-valuation
```

### 4.2 个股灰度

只灌 100 只，避免测试环境过重：

```bash
python -m etl.cli stock-universe --limit 100
python -m etl.cli stock-dividends-bulk --days 730
python -m etl.cli stock-metrics --limit 100
python -m etl.cli stock-industry --limit 100 --sina-only --sina-prefix sw_ --overwrite
```

### 4.3 管理员

```bash
python -m app.cli create-admin --email staging-admin@example.com
```

不要用生产管理员邮箱。

### 4.4 测试账号

手工注册一个：

```text
staging-user@example.com
```

如果 `AUTH_DEV_MODE=true`，验证 token 在 API 日志里。

---

## 5. 访问保护

### 方案 A：Cloudflare Access

在 Cloudflare：

```text
staging.stock.iamlay.com
→ Access → One-time PIN / Email
```

只允许团队邮箱访问。

### 方案 B：Basic Auth

在 Railway 前面加反向代理，或用 Cloudflare Worker。

### 禁止收录

Web 增加：

```text
X-Robots-Tag: noindex, nofollow
```

或 `robots.txt`：

```text
User-agent: *
Disallow: /
```

---

## 6. CI 与 E2E

### 6.1 GitHub Environment

GitHub → Settings → Environments → 新建：

```text
staging
```

变量：

```text
STAGING_BASE_URL=https://staging.stock.iamlay.com
STAGING_API_URL=https://<staging-api>.up.railway.app
STAGING_DATABASE_URL=<staging DB>
```

### 6.2 E2E

后续引入 Playwright，覆盖：

```text
登录
→ 自选
→ ETF 详情
→ 个股详情
→ 提醒设置
```

### 6.3 部署流程

```text
功能分支 push
→ staging 自动部署
→ 手工验收
→ 合并 main
→ 生产部署
```

---

## 7. 重置环境

### 方案 A：Railway 快照

初始化完成后，给 staging 数据库做一次快照。

测试坏了：

```text
恢复快照
```

### 方案 B：清库重建

```bash
alembic downgrade base
alembic upgrade head
python -m etl.cli seed
python -m etl.cli sync-all --start 2025-01-01 --delay 0.2
```

不要在生产执行。

---

## 8. 验收清单

- [ ] staging 域名可访问；
- [ ] API `/healthz` 200；
- [ ] `/dashboard` 真实数据；
- [ ] `/etf` 100 只；
- [ ] `/stocks` 有测试数据；
- [ ] 注册/登录可用；
- [ ] 自选可用；
- [ ] 提醒设置可用；
- [ ] 管理员可登录；
- [ ] 不连生产库；
- [ ] 不发送真实用户邮件；
- [ ] 搜索引擎不可收录。

---

## 9. 成本

| 项 | 估算 |
|---|---|
| Railway API | 低配即可 |
| Railway Web | 低配即可 |
| PostgreSQL | 小容量 |
| 合计 | 约 $5–15/月，以 Railway 页面为准 |

可以非工作时间暂停 staging 服务。

---

## 10. 建议顺序

```text
1. 建 staging 分支
2. 建独立 Railway 项目
3. 建独立 Postgres
4. 部署 API
5. 部署 Web
6. 配 staging 域名
7. 初始化 100 ETF + 100 股票
8. 建管理员账号
9. 加 Cloudflare Access
10. 跑验收清单
```
