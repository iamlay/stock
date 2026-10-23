# 部署手册

> 日常维护、故障排查、回滚请看 [运维操作手册](OPERATIONS.md)。：Vercel + Railway + GitHub Actions

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
| `STOCKLAB_AUTH_DEV_MODE` | `false`（邮箱登录不受影响；手机号验证码会返回 503） |
| `STOCKLAB_SMS_PROVIDER` | `none`（接入短信后改） |
| `STOCKLAB_GUEST_DAILY_LIMIT` | `20` |
| `STOCKLAB_FREE_DAILY_LIMIT` | `50` |
| `STOCKLAB_REGISTRATION_INVITE_CODE` | 可选；固定邀请码 |
| `STOCKLAB_REGISTRATION_INVITE_REQUIRED` | `true` 时注册必须使用有效邀请码 |
| `STOCKLAB_SMTP_HOST` | SMTP 主机，例如 `smtp.qq.com` |
| `STOCKLAB_SMTP_PORT` | `465`（SSL）或 `587`（STARTTLS） |
| `STOCKLAB_SMTP_USERNAME` | SMTP 登录名，通常是邮箱 |
| `STOCKLAB_SMTP_PASSWORD` | SMTP 授权码 / API Key，不是邮箱登录密码 |
| `STOCKLAB_SMTP_FROM` | 发件人，例如 `StockLab <hi@yourdomain.com>` |
| `STOCKLAB_SMTP_STARTTLS` | `true`（587 端口） |
| `STOCKLAB_SMTP_SSL` | `true`（465 端口） |
| `STOCKLAB_FRONTEND_URL` | 前端公网地址，用于拼接验证/重置链接 |

> `postgres://` / `postgresql://` 会被自动规范化为 `postgresql+psycopg://`，不需要手改。

### 2.2.1 邮箱服务（验证 + 重置密码）

生产环境必须配置 SMTP。常用免费方案：

| 服务 | 主机 | 端口 | 说明 |
|---|---|---|---|
| QQ 邮箱 | `smtp.qq.com` | `465` | `SMTP_SSL=true`，密码填授权码 |
| 163 邮箱 | `smtp.163.com` | `465` | 同上 |
| Gmail | `smtp.gmail.com` | `587` | `STARTTLS=true`，使用应用专用密码 |
| Resend | `smtp.resend.com` | `587` | 用户名 `resend`，密码 API Key，发件域名需验证 |

示例（QQ 邮箱）：

```text
STOCKLAB_SMTP_HOST=smtp.qq.com
STOCKLAB_SMTP_PORT=465
STOCKLAB_SMTP_USERNAME=your@qq.com
STOCKLAB_SMTP_PASSWORD=授权码
STOCKLAB_SMTP_FROM=StockLab <your@qq.com>
STOCKLAB_SMTP_SSL=true
STOCKLAB_SMTP_STARTTLS=false
STOCKLAB_FRONTEND_URL=https://stocklabweb-production.up.railway.app
```

未配置 SMTP 且 `AUTH_DEV_MODE=false` 时，注册会返回 503，不会创建无法验证的账号。

### 2.2.2 Railway 发不出邮件：改用 HTTPS API

Railway 容器可能无法访问 `smtp.qq.com:465`，日志表现为：

```text
OSError: [Errno 101] Network is unreachable
```

这不是授权码问题，是出站网络限制。改用 HTTPS 邮件 API：

**Resend（推荐，免费额度）**

1. 注册 [resend.com](https://resend.com)，验证域名（如 `iamlay.com`）；
2. 创建 API Key；
3. Railway 变量：

```text
STOCKLAB_EMAIL_PROVIDER=resend
STOCKLAB_RESEND_API_KEY=re_xxxxxxxx
STOCKLAB_EMAIL_FROM=StockLab <noreply@iamlay.com>
STOCKLAB_FRONTEND_URL=https://stock.iamlay.com
STOCKLAB_AUTH_DEV_MODE=false
```

**Brevo（可验证单个发件邮箱，不一定要域名）**

```text
STOCKLAB_EMAIL_PROVIDER=brevo
STOCKLAB_BREVO_API_KEY=xkeysib-xxxxxxxx
STOCKLAB_EMAIL_FROM=StockLab <your@163.com>
```

> `EMAIL_FROM` 必须与 Resend 验证的域名或 Brevo 验证的发件人一致。
> `FRONTEND_URL` 只能填一个地址，不能逗号并列。

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

### 3.1 自定义域名（示例：stock.iamlay.com）

前端绑定 `https://stock.iamlay.com` 后，API 侧同步改两个变量：

```text
STOCKLAB_CORS_ORIGINS=https://stock.iamlay.com
STOCKLAB_FRONTEND_URL=https://stock.iamlay.com
```

- `CORS_ORIGINS` 不更新，浏览器登录/注册会被 CORS 拦截；
- `FRONTEND_URL` 不更新，验证邮件和重置密码邮件里的链接仍指向旧域名；
- 旧域名如果还要保留，用逗号并列：`https://stock.iamlay.com,https://old.example.com`。

> 切换域名后，`localStorage` 里的 JWT 属于旧 origin，用户需要在新域名重新登录一次。

---

## 3.5 备选：Railway Cron 跑 ETL（不暴露数据库）

如果不想开 TCP Proxy，或 GitHub Actions 连不上公网数据库，可以直接在 Railway 内跑：

1. 同一项目 → **New → GitHub Repo** → 选同一个仓库；
2. 服务设置：
   - Root Directory：仓库根目录
   - Builder：Dockerfile
   - Dockerfile Path：`etl/Dockerfile`
3. 变量：

```text
STOCKLAB_DATABASE_URL=${{Postgres.DATABASE_URL}}
```

4. **Settings → Deploy → Custom Start Command**：

```bash
python -m etl.cli daily
```

5. **Settings → Cron Schedule**：

```text
30 10 * * 1-5
```

Railway Cron 使用 UTC，`10:30 UTC` 即北京时间 `18:30`。

6. 首次全量：把 Start Command 临时改成：

```bash
python -m etl.cli sync-all --start 2016-01-01 --delay 0.2 && python -m etl.cli sync-shares && python -m etl.cli sync-valuation
```

手动触发一次，跑完再改回 `daily`。

> 该方案不需要 `DATABASE_PUBLIC_URL`，也不需要 GitHub Secret。

## 3.6 邀请码过期 Cron（可选）

> 如果按 3.7 建一个 5 分钟维护 Cron，用 `etl.cli cron` 会同时处理邀请码过期，**不需要单独建本服务**。

每天把过期但未使用的邀请码标记为 `expired`。

1. 同一项目 → **New → GitHub Repo** → 选同一个仓库；
2. 服务设置：
   - Root Directory：仓库根目录
   - Builder：Dockerfile
   - Dockerfile Path：`apps/api/Dockerfile`
3. **Settings → Deploy → Custom Start Command**：

```bash
python -m app.cli expire-invites
```

4. **Settings → Cron Schedule**：

```text
0 19 * * *
```

Railway Cron 使用 UTC，`19:00 UTC` 即北京时间次日 `03:00`。

5. 变量：

```text
STOCKLAB_DATABASE_URL=${{Postgres.DATABASE_URL}}
```

6. 不需要公网域名，也不需要额外 Secret。

运行日志应出现：

```text
expired invites: 3
```

> 后台打开邀请码列表、批次、导出时也会惰性执行过期标记；Cron 只是保证没人访问时状态也能更新。

## 3.7 5 分钟最新报价 Cron（Railway）

1. 同一项目 → **New → GitHub Repo** → 选同一个仓库；
2. 服务设置：
   - Root Directory：仓库根目录
   - Builder：Dockerfile
   - Dockerfile Path：`apps/api/Dockerfile`
3. **Settings → Deploy → Custom Start Command**：

```bash
python -m etl.cli cron
```

`cron` 每次会：

1. 把过期未用邀请码标记为 `expired`；
2. 交易时段内刷新最新报价；
3. 非交易时段跳过报价，只做邀请码过期。

4. **Settings → Cron Schedule**：

```text
*/5 1-7 * * 1-5
```

- UTC 01:00–07:59 覆盖北京时间 09:00–15:59；
- 脚本内部会跳过午休、非交易日和收盘后；
- 不需要公网域名。

5. 变量：

```text
STOCKLAB_DATABASE_URL=${{Postgres.DATABASE_URL}}
```

日志应出现：

```text
cron: quotes=20 latest=2026-10-20T14:35:00 expired_invites=0
```

> 仓库根目录的 `railway.json` 指向 `apps/api/Dockerfile`，所以 cron 服务也复用这个镜像；镜像里已包含 `etl` 代码。
> 如果 Railway 仍按 `etl/Dockerfile` 构建，改成 `apps/api/Dockerfile`。
> 手动测试加 `--force`：`python -m etl.cli cron --force`。

---

## 4. GitHub Actions：ETL

工作流：`.github/workflows/etl.yml`

- 定时：工作日 18:30（北京时间）；
- 手动：Actions → ETL → Run workflow；
- 首次部署勾选 **full**，拉取 2016 年至今全量；
- 之后每天增量 30 天 + 份额 + 估值 + **个股最新价/股息率重算**；
- 个股分红：每周一 19:00 由 `stock-dividends.yml` 刷新。

个股相关任务：

| 工作流 | 时间 | 内容 |
|---|---|---|
| `etl.yml` | 工作日 18:30 | ETF 日线 + 个股价格/指标 |
| `stock-dividends.yml` | 周一 19:00 | 个股批量分红 + TTM 重算 |
| `stock-seed.yml` | 手动 | 首次灌 500 只 + 行业 |
| `stock-full.yml` | 手动 | 扩到 5,000 只 + 批量分红 + 粗行业 |
| `stock-bars.yml` | 每月 1 日 20:00 | 高股息前 2,000 只 K 线补全 |
| `stock-financials.yml` | 每月 1 日 21:00 | 全市场 5,000 只年报/季报 |
| `stock-industry-detail.yml` | 每季度首日 20:30 | 高股息前 500 只三级行业 |

必须配置的 Secret：

| Secret | 值 |
|---|---|
| `STOCKLAB_DATABASE_URL` | Railway `DATABASE_PUBLIC_URL`（带 `+psycopg` 和 `sslmode=require`） |
| `STOCKLAB_ALERT_WEBHOOK` | 可选，质量检查失败时的 Slack/Discord/飞书 Webhook |

---

## 5. 首次上线检查清单

- [ ] Railway API `/healthz` 返回 200
- [ ] Railway 日志无迁移错误
- [ ] GitHub Actions 手动跑一次 `full=true`，`etl.cli status` 有数据
- [ ] 创建管理员：本地或 CI 执行
      `STOCKLAB_DATABASE_URL=... python -m app.cli create-admin --phone 139xxxxxxxx`
- [ ] 用邮箱注册/登录 → 个人中心 → 生成兑换码 → 兑换 → 回测 → 历史
- [ ] 未验证邮箱登录返回 403，验证后可登录
- [ ] 收到验证邮件，点击链接后个人中心显示“已验证”
- [ ] 退出登录 → 忘记密码 → 收到重置邮件 → 设置新密码 → 旧密码失效
- [ ] Vercel 域名加入 CORS
- [ ] 手机号验证码登录在短信服务接入前应返回 503（`AUTH_DEV_MODE=false`）
- [ ] 页脚可打开用户协议、隐私政策、免责声明
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

## 7. 常见错误

### `The executable pnpm could not be found`

这不是 API 代码的问题，而是 Railway 没有走 Dockerfile，正在用 Nixpacks 或自定义 Start Command 启动仓库。

修复顺序：

1. **Service → Settings → Source**
   - Root Directory 留空（仓库根目录），不要选 `apps/api`。
2. **Service → Settings → Build**
   - Builder 选 `Dockerfile`
   - Dockerfile Path 填 `apps/api/Dockerfile`
3. **Service → Settings → Deploy**
   - Custom Start Command **清空**（使用 Dockerfile 里的 uvicorn 命令）
   - Healthcheck Path 填 `/healthz`
4. 重新 Deploy。

构建日志应该出现：

```text
Using Dockerfile
...
Successfully built ...
```

启动日志应该是：

```text
alembic upgrade head
INFO:     Uvicorn running on http://0.0.0.0:8000
```

而不是 `pnpm install` / `pnpm start`。

> 如果 Root Directory 必须是 `apps/api`，当前 Dockerfile 不适用（它按仓库根目录复制 `apps/api/...`）。此时要么把 Root Directory 改回仓库根目录，要么单独维护一份 context 为 `apps/api` 的 Dockerfile。

### Vercel 构建找不到 workspace

见第 3 节的 pnpm workspace 配置。

### 页面仍显示「示例数据」

API 已返回真实数据，但 Next.js 服务端组件连不上 API，通常是 Web 服务缺少：

```text
API_BASE_URL=https://你的-api.up.railway.app
```

`NEXT_PUBLIC_API_BASE_URL` 只影响浏览器，服务端组件用的是 `API_BASE_URL`。
检查变量没有末尾 `/`，保存后重新部署 Web。

---

## 8. 已知限制

- Railway 容器启动时会跑迁移，多副本部署会并发执行；当前单副本没问题。
- GitHub Actions 依赖 Railway 公网数据库，需确保 `DATABASE_PUBLIC_URL` 可用。
- Vercel Preview 域名默认被 CORS 拦截，需配置 `CORS_ORIGIN_REGEX` 或手动加域名。
- `NEXT_PUBLIC_API_BASE_URL` 是构建时变量，换 API 域名要重新部署前端。
- 本方案不包含短信服务商、支付回调、对象存储。
