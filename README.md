<div align="center">

# StockLab

**面向稳健型投资者的 A 股 ETF 投研平台**

行情 · 估值 · ETF 数据中心 · 可复现的策略回测 · 兑换制会员

</div>

---

> ## 📌 置顶 · 完整开发计划
>
> ### **[docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md)**
>
> **v1.2 · 2026-10-19 · 目标上线 2027-01-22**
>
> 14 周、4 个阶段、10 个 Epic：产品范围、技术架构、数据体系、模块设计、排期、测试、合规、运维与风险。
> 本文件是项目唯一事实来源（SSOT），每次迭代评审后更新。

---

## 项目简介

参考 [稳稳地赢](https://wenwendeying.com/) 的产品形态，做一个**更透明、更好读、更适合移动端**的 ETF 投研工具：

- **看得懂**：每个指标都有口径说明，结论先行，不堆术语。
- **可复现**：策略规则、参数、成交假设全部公开，回测结果可自行验证。
- **不荐股**：只提供数据与规则推演，不构成投资建议。

MVP 聚焦 **ETF（红利 / 现金流 / 跨境 / 宽基 / 行业）**，数据模型预留个股，V2 扩展。

## 已确认决策（2026-10-19）

| 决策 | 结论 |
|---|---|
| 范围 | **MVP 只做 ETF**，个股延至 V2 |
| 登录 | **邮箱 + 密码**；手机号验证码保留，待短信服务接入后启用 |
| 支付 | **站内不收款**，不接微信支付/支付宝；第三方平台代收 + 兑换码 |
| 主体 | 暂无；个体户按需注册，仅用于备案与开票 |

## 项目状态

| 项 | 状态 |
|---|---|
| 阶段 | ✅ W52 Vercel Analytics |
| 范围 | ✅ MVP 仅 ETF |
| 文档 | ✅ 开发计划 v1.2 + ADR-0008 + [部署手册](docs/DEPLOYMENT.md) |
| Web | ✅ 邮箱登录/注册 / 兑换 / 历史 / 兑换码 / 订单 / 用户 / 邀请码后台 |
| API | ✅ 行情、ETF、估值、回测、会员、后台、订单、自选、对比、个股，108 个测试 |
| 数据 | ✅ 34,374 行日线 + 20 条份额快照 + 6 个指数估值 |
| 部署 | ✅ Vercel 前端 · Railway API/PG · GitHub Actions ETL |
| 上线 | ⬜ 计划 2027-01-22 |

## 快速开始

```bash
# Web（需 Node 20+ / pnpm 11）
pnpm install
pnpm --filter @stocklab/web dev        # http://localhost:3000

# API（Python 3.12）
python -m venv .venv
.venv\Scripts\activate                 # macOS/Linux: source .venv/bin/activate
pip install -e "apps/api[dev]"
uvicorn app.main:app --app-dir apps/api --reload --port 8000

# 测试
pytest apps/api -q
ruff check apps/api etl

# 数据库 + 迁移（PostgreSQL）
docker compose -f infra/docker-compose.yml up -d db redis
alembic -c apps/api/alembic.ini upgrade head

# 数据管道
python -m etl.cli seed
python -m etl.cli sync-all --start 2016-01-01 --delay 0.2
python -m etl.cli sync-shares
python -m etl.cli sync-quotes
python -m etl.cli sync-valuation
python -m etl.cli status
python -m etl.cli quality --limit 20
```

> 非 Docker 环境可用本地 PostgreSQL，并通过 `STOCKLAB_DATABASE_URL` 指定连接串；
> 参考 `.env.example`。

## 数据管道（W2–W3）

| 项 | 状态 |
|---|---|
| 覆盖 | 20 只 ETF，2016-01-04 → 2026-10-19，34,374 行日线 + 20 条份额 + 6 个指数估值 |
| 数据源 | 东财日线为主、腾讯兜底；份额来自腾讯快照；估值来自蛋卷 |
| 幂等 | 按窗口删除重插，重复同步不产生重复行 |
| 可观测 | `data_jobs`（每次任务）+ `data_quality_checks`（4–8 项/次） |
| 指标 | MA5/20/60、20 日波动、近 1 年回撤、1/3/12 月收益、52 周高低、PE/PB 分位 |
| 校验 | OHLC、重复、顺序、正价格、成交量、份额、新鲜度 |

详见 [etl/README.md](etl/README.md)。

## 5 分钟最新报价（W29）

- 新增表 `realtime_quotes`，只存最新价、昨收、涨跌、成交额、报价时间；
- ETL `sync-quotes` 用腾讯批量行情刷新 20 只 ETF，不覆盖 `market_daily`；
- 交易时段守卫：周末、非交易时间、非交易日自动跳过；
- API `/etfs`、`/etfs/{code}`、`/market/overview` 优先使用最新报价，并返回 `quote_time`；
- 前端显示「更新 HH:MM」，日线指标与回测仍按日频。

Railway Cron 每 5 分钟执行一个统一入口：

```bash
python -m etl.cli cron
```

它会先处理邀请码过期，再在交易时段刷新最新报价；不需要为每个任务单独建 Cron 服务。

手动测试可加 `--force` 跳过交易时段限制。

## W3 API

| 接口 | 说明 |
|---|---|
| `GET /api/v1/etfs` | 20 只 ETF + 最新价、涨跌、均线、回撤、规模、份额 |
| `GET /api/v1/etfs/{code}` | 详情 + 120 根日线 + 1/3/12 月收益 |
| `GET /api/v1/market/overview` | 重点 ETF 等权涨跌、涨跌家数、成交额、领涨/领跌 |
| `GET /api/v1/market/industries` | 申万一级行业个股等权涨跌 |
| `GET /api/v1/stocks` | 个股列表，按 TTM 股息率/市值/PE 排序，支持行业筛选 |
| `GET /api/v1/stocks/{code}` | 个股详情 + 分红历史 |
| `GET/POST/DELETE /api/v1/stock-watchlist` | 个股自选 |
| `GET /api/v1/data/status` | 行数、最新交易日、份额快照、最近任务 |
| `POST /api/v1/auth/register` | 邮箱 + 密码注册，发送验证邮件，**不返回 JWT** |
| `POST /api/v1/auth/login/email` | 邮箱 + 密码登录（需已验证） |
| `POST /api/v1/auth/verify-email` | 验证邮箱 token |
| `POST /api/v1/auth/bind-phone` | 登录后绑定手机号（需密码确认） |
| `POST /api/v1/auth/resend-verification` | 按邮箱重发验证邮件（公开） |
| `POST /api/v1/auth/forgot-password` | 发送密码重置邮件 |
| `POST /api/v1/auth/reset-password` | 用 token 设置新密码 |
| `POST /api/v1/auth/sms-code` | 发送验证码；**dev 模式返回 code** |
| `POST /api/v1/auth/login` | 手机号 + 验证码换 JWT（保留） |
| `GET /api/v1/me` | 当前用户（Bearer） |

前端通过 `API_BASE_URL` 服务端拉取；API 不可用时自动回退到示例数据。

## 自选（W23）

- `/watchlist`：登录后查看自选 ETF 的价格、涨跌、MA20、规模；
- ETF 详情页「加入自选」按钮，支持加入/取消；
- 自选按最近加入排序，空状态引导去 ETF 列表；
- 表 `watchlist_items`，唯一约束 `(user_id, code)`；用户删除时级联清理。

接口：`GET/POST /api/v1/watchlist`、`DELETE /api/v1/watchlist/{code}`。

## ETF 对比（W24）

`/etf/compare?codes=510300,510500&days=250`：

- 选择 2–5 只 ETF；
- 同一时间窗口归一化到 100；
- 展示累计收益、最大回撤、年化波动；
- 多线 SVG 图 + 指标表，可跳转详情；
- 支持近 3 月 / 6 月 / 1 年 / 2 年。

接口：`GET /api/v1/etfs/compare?codes=...&days=250`。

## 回测引擎（W5）
代码在 `apps/api/app/quant`，纯 Python、无第三方指标依赖。

| 项 | 规则 |
|---|---|
| 成交 | T 日收盘出信号，T+1 开盘成交 |
| 成本 | 佣金 0.02%（最低 5 元）+ 滑点 2bp |
| 约束 | T+1、100 份整数倍、停牌/涨跌停不成交、最小调仓 0.5% |
| 指标 | 累计/年化收益、最大回撤、波动率、夏普、仓位暴露、胜率 |
| 策略 | 买入持有、双均线、RSI、布林带、MACD、偏离度调仓、每月定投、滚动网格 |
| 参数 | 详情页按 API schema 自动渲染参数输入，提交即重跑 |

```bash
GET  /api/v1/backtests/strategies
POST /api/v1/backtests
{"code":"510300","strategy":"dual-ma","start":"2020-01-01","params":{"fast":20,"slow":60}}
```

策略详情页 `/strategies/dual-ma` 可直接选标的、改参数与起始日期并运行真实回测；定投与网格也支持参数（月数、窗口、档位）。

## 策略实验室列表（W25）

- `/strategies` 服务端调用 `GET /api/v1/backtests/summary?code=...`；
- 顶部下拉可切换回测标的（20 只 ETF），URL 使用 `?code=510880`；
- 8 个策略在所选标的上真实回测，卡片展示累计、年化、最大回撤、夏普、同期基准；
- 卡片曲线取真实净值并归一化到 100；
- 详情页净值图叠加虚线基准，个人中心历史快照也显示基准；
- 点击卡片进入详情时自动带上当前标的 `?code=...`；
- API 不可用时回退到示例卡片，并标注“API 未连接”。

## 回测持久化与会员墙

| 项 | 规则 |
|---|---|
| 落库 | 每次回测写 `backtest_runs`（含参数、指标、净值、交易、quota） |
| 游客 | 20 次/日（按 IP 哈希） |
| 免费用户 | 50 次/日 |
| 会员 | 不限次数，可查看历史 |
| 超额 | 429 + `quota`，前端显示剩余次数与"了解会员" |
| 历史 | `GET /api/v1/backtests/history`、`/history/{id}`，仅会员 |

用户表新增 `plan`、`plan_expires_at`；会员判定为 `plan=member` 且未过期。

## 兑换码 → 会员 → 历史

```bash
# 生成兑换码（服务端 CLI）
python -m app.cli gen-codes --count 10 --days 365 --channel zhishixingqiu

# 管理员：先在网站注册邮箱，再提升为 admin
python -m app.cli create-admin --email admin@example.com

# 旧手机号管理员（保留）
python -m app.cli create-admin --phone 13900139000

# 用户登录后兑换
POST /api/v1/redeem   {"code":"SLXXXXXXXXXX"}
```

- 兑换码表：`redeem_codes`，支持批次、渠道、次数、绑定用户、过期时间；
- 兑换事务内行锁 + 次数校验，会员时长可叠加；
- 登录页已接 API：开发模式自动回填验证码；
- `/account`：会员状态、兑换入口、历史列表、点开看净值与指标。

## 管理员登录

1. 先在 `/login` 用邮箱注册普通账号；
2. 在服务器或本地对生产库执行：

```bash
STOCKLAB_DATABASE_URL="postgresql+psycopg://..." \
  python -m app.cli create-admin --email admin@example.com
```

3. 用该邮箱正常登录；
4. 个人中心会出现「兑换码管理」，或直接访问：

```text
/admin/redeem-codes
/admin/orders
/admin/users
```

> 没有独立的管理员登录入口，管理员和普通用户走同一个 `/login`，靠 `role=admin` 区分。

浏览器侧 API 地址由 `NEXT_PUBLIC_API_BASE_URL` 指定（构建时注入）。

## 后台兑换码管理

`/admin/redeem-codes`（仅 `role=admin`）：

- 批量生成：数量、会员天数、码有效期、渠道、套餐；
- 统计：总数 / 未使用 / 已兑换 / 已过期 / 已作废；
- 列表：分页（10/页）、状态 / 批次 / 兑换码搜索；
- 批次汇总下拉，支持按批次导出 CSV；
- 单码作废、一键复制本批次；
- 操作审计：生成、作废、导出、订单、退款全部留痕（操作人、对象、IP、时间）。

接口：`GET/POST /api/v1/admin/redeem-codes`、`/batches`、`/{code}/revoke`、`/export`、`/audit-logs`。

## 订单 / 支付流水

`/admin/orders`：

- 登记第三方平台订单（知识星球 / 小鹅通 / 手动），填写外部单号、买家手机号或邮箱、金额；
- 登记即生成一张绑定订单的兑换码；买家手机号/邮箱已注册时自动绑定账号；
- 订单列表分页、按平台/状态/关键词筛选，统计已交付收入与客单价；
- 退款：订单置为 refunded，未使用的兑换码同步作废。

接口：`POST/GET /api/v1/admin/orders`、`POST /api/v1/admin/orders/{order_no}/refund`。

## 用户管理

`/admin/users`：

- 按邮箱/手机号搜索，按套餐、状态筛选，分页；
- 封禁 / 解封：`users.status = banned` 后旧 JWT 立即失效；
- 开通/续费会员：选择天数，按当前到期日叠加；
- 取消会员：置为 `free`，清空到期日；
- 所有操作写入 `admin_audit_logs`，不能封禁自己。
- 点击账号进入 `/admin/users/{id}`，聚合该用户的：
  - 订单（按 `user_id`、买家手机号或买家邮箱匹配）；
  - 兑换码（绑定、兑换、关联订单）；
  - 回测历史（策略、标的、收益、交易数），点「查看」弹窗展示净值曲线与交易明细。
- 三个区块各自分页，10 条/页，接口返回 `total` 与 `page`。

接口：`GET /api/v1/admin/users`、`PATCH /api/v1/admin/users/{id}`、`GET /api/v1/admin/users/{id}`、`/orders`、`/codes`、`/backtests`。

## 邀请码批次

`/admin/invites`：

- 批量生成：数量、每码可用次数、有效期、备注、可选绑定邮箱/手机号；
- 统计：总数 / 未使用 / 已用完 / 已过期 / 已作废；
- 批次备注统计：每个批次的总数、未使用、已用完、已过期、已作废；
- 按批次、状态筛选，单码/整批作废，一键复制；
- 导出 CSV（可按状态/批次过滤）；
- 每个邀请码可查看使用记录：邮箱、手机号、用户 ID、IP、时间；
- 注册时校验绑定身份并原子扣减使用次数；
- 列表/批次/导出时自动把过期未用码标记为 `expired`；也可手动执行 `python -m app.cli expire-invites`，Railway Cron 每天 03:00（北京时间）自动跑一次。

接口：`GET/POST /api/v1/admin/invites`、`/batches`、`/batches/{id}/revoke`、`/{code}/revoke`、`/{code}/usages`、`/export`。

启用强制邀请：

```text
STOCKLAB_REGISTRATION_INVITE_REQUIRED=true
```

`STOCKLAB_REGISTRATION_INVITE_CODE` 仍可作为固定的环境变量邀请码保留。

## 登录（W15）

- 主路径：**邮箱 + 密码**注册/登录，密码用 `scrypt` 加盐哈希存储。
- 注册时可填可选手机号，用于匹配手机号邀请码；登录后可在个人中心用密码确认绑定手机号。
- **邮箱未验证不能登录**：注册只发验证邮件、不返回 JWT；验证成功后回到登录页。
- 邮箱验证链接 24 小时有效；`/verify-email/sent` 可按邮箱重发。
- 忘记密码：邮件重置链接 30 分钟有效；重置后 `token_version` 递增，旧密码和所有旧 JWT 立即失效。
- 手机号 + 6 位验证码登录保留；短信服务接入前，生产环境设置 `STOCKLAB_AUTH_DEV_MODE=false` 后该接口返回 503。
- 开发模式不连 SMTP，验证/重置 token 直接返回给前端，便于本地联调。
- 生产环境必须配置 `STOCKLAB_SMTP_*` 或 `STOCKLAB_EMAIL_PROVIDER=resend|brevo`，否则注册返回 503。
- 注册、登录、忘记密码、重发验证均有频率限制（`rate_limit_events` 表），超限返回 429。
- 可选邀请码：设置 `STOCKLAB_REGISTRATION_INVITE_CODE` 后，注册必须携带 `invite_code`。
- 邀请码批次：`/admin/invites` 生成、查看、作废；设置 `STOCKLAB_REGISTRATION_INVITE_REQUIRED=true` 后，注册必须使用有效邀请码。

| 动作 | 限制 |
|---|---|
| 注册 | 20 次/小时/IP，3 次/小时/邮箱 |
| 邮箱登录 | 30 次/15 分钟/IP，10 次/15 分钟/账号 |
| 忘记密码 | 20 次/小时/IP，5 次/小时/邮箱 |
| 重发验证 | 10 次/小时/IP，5 次/小时/邮箱 |
| 短信验证码 | 5 次/小时/手机号 |

## 工作台真实化（W27）

- 顶部统计、重点 ETF 表格使用真实行情；
- 「ETF 分类热力」改为 20 只重点 ETF 按分类等权涨跌，不再冒充申万行业；
- 「市场温度」由重点 ETF 等权涨跌 + 涨跌家数估算，并标注为情绪参考；
- 「策略速览」接 `/backtests/summary` 真实回测；
- API 不可用时仍回退示例，并标注 `API_BASE_URL` 检查提示。

## 首页真实数据（W28）

- 顶部 ticker、重点 ETF 表格使用真实行情；
- Hero 卡片展示 510300 的 PE、股息率、近 1 年收益与真实净值曲线；
- 策略旗舰卡片使用 `/backtests/summary` 的真实回测；
- API 不可用时才回退示例，并明确标注；
- 会员价格卡片仍是产品文案，不属于行情数据。

## 法务页面（W26）

- `/legal/terms`：用户协议；
- `/legal/privacy`：隐私政策；
- `/legal/disclaimer`：免责声明；
- 页脚、登录页均已链接；`/legal` 自动跳转用户协议。

内容按当前实际能力编写：无站内支付、无微信登录、邮箱/手机号收集范围、数据来源与回测局限、第三方委托处理。

> 正式公开运营前建议请专业人士审核一遍。

## 目录结构

```text
stock/
├─ apps/
│  ├─ web/              # Next.js 15：公开页 SSR + 工作台
│  └─ api/              # FastAPI + 测试
├─ packages/            # （规划）quant / contracts / ui
├─ etl/                 # 数据管道：采集、校验、CLI
├─ infra/               # docker-compose（PG / Redis / API / Web）
├─ docs/                # 开发计划、ADR、ETF 清单
└─ .github/             # CI（typecheck/build + lint/test）
```

## 技术栈

| 层 | 选型 |
|---|---|
| Web | Next.js 15 (App Router) · React 19 · TypeScript · Tailwind CSS 4 |
| API | Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · Pydantic v2（Celery 于 W3 接入） |
| 数据 | PostgreSQL 16 · Redis 7（compose 已就绪）· Polars / Pandas |
| 量化 | 自研日频回测引擎（T+1、成本、停牌、分红再投） |
| 会员 | 兑换码；**无站内支付、无微信登录** |
| 交付 | pnpm + Turborepo · Docker Compose · GitHub Actions |

## 快速导航

| 文档 | 说明 |
|---|---|
| [开发计划](docs/DEVELOPMENT_PLAN.md) | 总纲：范围、架构、数据、模块、排期、风险 |
| [ETF 覆盖清单](docs/etf-universe.md) | 首批 20 只标的与字段 |
| [商业化方案](docs/DEVELOPMENT_PLAN.md#17-无主体无站内支付的商业化方案) | 无主体、无站内支付如何变现 |
| [部署手册](docs/DEPLOYMENT.md) | Vercel + Railway + GitHub Actions |
| [运维操作手册](docs/OPERATIONS.md) | 部署、迁移、定时任务、备份、故障排查、回滚 |
| [测试环境方案](docs/STAGING.md) | 独立 Railway staging、隔离数据库、E2E 与验收 |
| [Vercel Analytics](docs/ANALYTICS.md) | 统计接入方式、Vercel 迁移限制与验收 |
| [个股股息率模块计划](docs/STOCK_MODULE_PLAN.md) | V2：股票池、股息率排序、数据模型与排期 |
| [个股 Phase 0 报告](docs/STOCK_PHASE0_REPORT.md) | 全市场列表/分红/日线数据源验证结果 |
| [个股行业 Phase 0 报告](docs/STOCK_INDUSTRY_PHASE0_REPORT.md) | 行业字段来源、覆盖率与补全策略 |
| [个股 Phase 1 报告](docs/STOCK_PHASE1_REPORT.md) | 500 只灰度、7,181 条分红、431 只股息率 |
| [个股行业 Phase 1.5 报告](docs/STOCK_INDUSTRY_PHASE1_REPORT.md) | 500 只行业补全，500/500 成功 |
| [个股 Phase 2 报告](docs/STOCK_PHASE2_REPORT.md) | 列表/详情/管理 API，97 个测试 |
| [个股 Phase 3 报告](docs/STOCK_PHASE3_REPORT.md) | 列表/详情/自选/管理页面 |
| [个股全市场报告](docs/STOCK_FULL_MARKET_REPORT.md) | 5,000 只扩量、批量分红、生产工作流 |
| [个股数据质量](docs/STOCK_QUALITY_REPORT.md) | 股息率/价格/行业/分红/时效检查 |
| [备份与安全](docs/BACKUP_SECURITY.md) | 加密备份、恢复演练、密钥轮换、DB 公网收口 |
| [自选提醒](docs/STOCK_ALERTS.md) | 涨跌/除息站内提醒，可选邮件 |
| [ETF 100 只](docs/ETF_100.md) | 100 只精选 ETF 分类、启用步骤与验收 |
| [部署手册](docs/DEPLOYMENT.md) | 含个股每日/每周定时任务 |
| [ADR-0008](docs/adr/0008-monetization-without-entity.md) | 登录与商业化的决策记录 |
| [页面地图](docs/DEVELOPMENT_PLAN.md#附录-a页面地图) | 全部路由与权限 |

## 许可

[Apache-2.0](LICENSE)
