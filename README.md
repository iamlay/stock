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
| 登录 | **手机号 + 验证码**，不接微信登录、不接第三方 OAuth |
| 支付 | **站内不收款**，不接微信支付/支付宝；第三方平台代收 + 兑换码 |
| 主体 | 暂无；个体户按需注册，仅用于备案与开票 |

## 项目状态

| 项 | 状态 |
|---|---|
| 阶段 | ✅ Sprint 0 骨架完成，进入 W2 数据管道 |
| 范围 | ✅ MVP 仅 ETF |
| 文档 | ✅ 开发计划 v1.2 + ADR-0008 |
| Web | ✅ 首页 / 工作台 / ETF / 策略 / 登录 / 定价（示例数据） |
| API | ✅ FastAPI 健康检查、套餐、行情概览 + 测试 |
| 数据 | ✅ 东财日线探针（510300，2,619 行） |
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
ruff check apps/api

# 数据源探针
python etl/probe_eastmoney.py --code 510300
```

## 目录结构

```text
stock/
├─ apps/
│  ├─ web/              # Next.js 15：公开页 SSR + 工作台
│  └─ api/              # FastAPI + 测试
├─ packages/            # （规划）quant / contracts / ui
├─ etl/                 # 数据探针与后续数据管道
├─ infra/               # docker-compose（PG / Redis / API / Web）
├─ docs/                # 开发计划、ADR、ETF 清单
└─ .github/             # CI（typecheck/build + lint/test）
```

## 技术栈

| 层 | 选型 |
|---|---|
| Web | Next.js 15 (App Router) · React 19 · TypeScript · Tailwind CSS 4 |
| API | Python 3.12 · FastAPI · Pydantic v2（SQLAlchemy/Celery 于 W2 接入） |
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
| [ADR-0008](docs/adr/0008-monetization-without-entity.md) | 登录与商业化的决策记录 |
| [页面地图](docs/DEVELOPMENT_PLAN.md#附录-a页面地图) | 全部路由与权限 |

## 许可

[Apache-2.0](LICENSE)
