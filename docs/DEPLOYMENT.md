# 部署手册：Vercel + Railway + GitHub Actions

> 架构：Next.js 部署 Vercel；FastAPI + PostgreSQL 部署 Railway；ETL 由 GitHub Actions 定时触发。

```text
浏览器
  │
  ├─ Vercel (Next.js, SSR)
  │      │ API_BASE_URL / NEXT_PUBLIC_API_BASE_URL
  │      ▼
  └─ Railway (FastAPI + PostgreSQL)

GitHub Actions ──(公网 DATABASE_URL)──► Railway PostgreSQL
```

---

## 1. 前置条件

- GitHub 仓库：`iamlay/stock`
- Railway 账号（Hobby 即可）
- Vercel 账号（商业用途需 Pro）
- 一个可用的域名（可选）

---

## 2. Railway：API + PostgreSQL

### 2.1 创建项目

1. Railway → **New Project** → **Deploy from GitHub repo** → 选择 `iamlay/stock`。
2. 服务设置：
   - **Root Directory**：仓库根目录（留空）
   - Railway 会自动读取根目录的 `railway.json`，使用 `apps/api/Dockerfile`。
3. 同一项目内 **New → Database → PostgreSQL**。

### 2.2 配置 API 变量

在 API 服务的 **Variables** 中添加：

| 变量 | 值 |
|---|---|
| `STOCKLAB_DATABASE_URL` | `${{Postgres.DATABASE_URL}}`（Railway 引用变量） |
| `STOCKLAB_ENV` | `production` |
| `STOCKLAB_CORS_ORIGINS` | `https://你的域名.vercel.app` |
| `STOCKLAB_CORS_ORIGIN_REGEX` | `https://.*\.vercel\.app`（可选，放行 Preview） |
| `STOCKLAB_JWT_SECRET` | 随机 32 字节以上 |
| `STOCKLAB_OTP_SECRET` | 另一条随机 32 字节 |
| `STOCKLAB_AUTH_DEV_MODE` | 私测可 `true`；公开必须 `false` |
| `STOCKLAB_SMS_PROVIDER` | `none`（接入短信后改） |
| `STOCKLAB_GUEST_DAILY_LIMIT` | `20` |
| `STOCKLAB_FREE_DAILY_LIMIT` | `50` |

> `postgres://` / `postgresql://` 会被自动规范化为 `postgresql+psycopg://`，不需要手改。

### 2.3 生成域名

API 服务 → **Settings → Networking → Generate Domain**，得到：

```text
https://stocklab-api-production-xxxx.up.railway.app
```

访问 `/healthz` 应返回：

```json
{"status":"ok","service":"stocklab-api","version":"0.1.0"}
```

### 2.4 迁移

容器启动命令已包含 `alembic upgrade head`，首次部署自动建表。若失败，查看 Deploy Logs。

### 2.5 数据库公网地址（给 GitHub Actions）

PostgreSQL 服务 → **Variables** → 复制 `DATABASE_PUBLIC_URL`，改写成：

```text
postgresql+psycopg://postgres:密码@xxx.proxy.rlwy.net:PORT/railway?sslmode=require
```

存入 GitHub Secret：`STOCKLAB_DATABASE_URL`。

---

## 3. Vercel：前端

1. Vercel → **Add New Project** → 导入 `iamlay/stock`。
2. **Root Directory** 选择 `apps/web`。
3. Framework 自动识别 Next.js；若未识别，手动选 Next.js。
4. 环境变量（Production / Preview 都加）：

| 变量 | 值 |
|---|---|
| `API_BASE_URL` | Railway API 域名（服务端 SSR 用） |
| `NEXT_PUBLIC_API_BASE_URL` | 同一个 Railway API 域名（浏览器用） |

5. Deploy。

> 若 Vercel 提示找不到 pnpm workspace：
> - 项目设置里开启 **Include source files outside of the Root Directory**；
> - Install Command 改为 `cd ../.. && pnpm install --frozen-lockfile`；
> - Build Command 改为 `cd ../.. && pnpm --filter @stocklab/web build`。

6. 绑定自定义域名后，把新域名加入 Railway 的 `STOCKLAB_CORS_ORIGINS`（逗号分隔）。

---

## 4. GitHub Actions：ETL

工作流：`.github/workflows/etl.yml`

- 定时：工作日 18:30（北京时间）；
- 手动：Actions → ETL → Run workflow；
- 首次部署勾选 **full**，拉取 2016 年至今全量；
- 之后每天增量 30 天 + 份额 + 估值。

必须配置的 Secret：

| Secret | 值 |
|---|---|
| `STOCKLAB_DATABASE_URL` | Railway `DATABASE_PUBLIC_URL`（带 `+psycopg` 和 `sslmode=require`） |

---

## 5. 首次上线检查清单

- [ ] Railway API `/healthz` 返回 200
- [ ] Railway 日志无迁移错误
- [ ] GitHub Actions 手动跑一次 `full=true`，`etl.cli status` 有数据
- [ ] 创建管理员：本地或 CI 执行
      `STOCKLAB_DATABASE_URL=... python -m app.cli create-admin --phone 139xxxxxxxx`
- [ ] 登录 → 个人中心 → 生成兑换码 → 兑换 → 回测 → 历史
- [ ] Vercel 域名加入 CORS
- [ ] `STOCKLAB_AUTH_DEV_MODE=false` 前先接短信，否则登录会 503
- [ ] 备份 Railway PostgreSQL（每日自动备份需在 Railway 开启）

---

## 6. 成本

| 项 | 费用 |
|---|---|
| Railway API（0.25 vCPU / 512 MB） | ≈ $10/月 |
| Railway PostgreSQL（0.25 vCPU / 512 MB + 10 GB） | ≈ $12/月 |
| Vercel（商业用途 Pro） | $20/月 |
| GitHub Actions | 免费额度足够 |
| **合计** | **≈ $42/月** |

如果 PostgreSQL 用 Neon 免费版，可降到 ≈ $30/月。

---

## 7. 已知限制

- Railway 容器启动时会跑迁移，多副本部署会并发执行；当前单副本没问题。
- GitHub Actions 依赖 Railway 公网数据库，需确保 `DATABASE_PUBLIC_URL` 可用。
- Vercel Preview 域名默认被 CORS 拦截，需配置 `CORS_ORIGIN_REGEX` 或手动加域名。
- `NEXT_PUBLIC_API_BASE_URL` 是构建时变量，换 API 域名要重新部署前端。
- 本方案不包含短信服务商、支付回调、对象存储。
