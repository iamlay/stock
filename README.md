<div align="center">

# StockLab

**面向稳健型投资者的 A 股 ETF 投研平台**

行情 · 估值 · ETF 数据中心 · 可复现的策略回测 · 会员订阅

</div>

---

> ## 📌 置顶 · 完整开发计划
>
> ### **[docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md)**
>
> **v1.1 · 2026-10-19 · 目标上线 2027-01-22**
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
| 经营主体 | **暂无** → 过渡期用「邀请码 / 兑换码 + 第三方平台代收」，支付与微信扫码登录延后 |
| 变现 | 先验证付费意愿，再接入自有支付（见[第 17 节](docs/DEVELOPMENT_PLAN.md#17-无主体阶段的商业化方案)） |

## 项目状态

| 项 | 状态 |
|---|---|
| 阶段 | 🚧 规划与基建（Sprint 0） |
| 范围 | ✅ MVP 仅 ETF |
| 主体 | ⬜ 暂无（过渡方案已定） |
| 文档 | ✅ 开发计划 v1.1 |
| 代码 | ⬜ 脚手架待初始化 |
| 上线 | ⬜ 计划 2027-01-22 |

## 快速导航

| 文档 | 说明 |
|---|---|
| [开发计划](docs/DEVELOPMENT_PLAN.md) | 总纲：范围、架构、数据、模块、排期、风险 |
| [页面地图](docs/DEVELOPMENT_PLAN.md#附录-a页面地图) | 全部路由与权限 |
| [数据字典](docs/DEVELOPMENT_PLAN.md#附录-b核心表-ddl-草案) | 核心表结构 |
| [策略清单](docs/DEVELOPMENT_PLAN.md#附录-c策略清单) | V1 / V2 策略与参数 |
| [商业化过渡方案](docs/DEVELOPMENT_PLAN.md#17-无主体阶段的商业化方案) | 无主体阶段如何收款与交付 |
| [ADR-0008](docs/adr/0008-monetization-without-entity.md) | 无主体商业化的决策记录 |
| [行动清单](docs/DEVELOPMENT_PLAN.md#15-本周行动清单sprint-0) | Sprint 0 每日任务 |

## 规划中的技术栈

| 层 | 选型 |
|---|---|
| Web | Next.js 15 (App Router) · React 19 · TypeScript · Tailwind CSS · shadcn/ui · ECharts |
| API | Python 3.12 · FastAPI · SQLAlchemy 2 · Pydantic v2 · Celery |
| 数据 | PostgreSQL 16 · Redis 7 · Polars / Pandas · Parquet (OSS) |
| 量化 | 自研日频回测引擎（T+1、成本、停牌、分红再投） |
| AI | DeepSeek API · pgvector RAG · 人工审核后发布 |
| 交付 | pnpm + Turborepo · uv · Docker Compose · GitHub Actions · GHCR · 阿里云 |

## 规划中的目录结构

```text
stock/
├─ apps/
│  ├─ web/              # Next.js 前端（公开页 SSR + 工作台 CSR）
│  └─ api/              # FastAPI 后端
├─ packages/
│  ├─ quant/            # 回测引擎（Python 包）
│  ├─ contracts/        # OpenAPI 生成的 TS 客户端与类型
│  └─ ui/               # 共享组件
├─ etl/                 # 数据采集、清洗、调度
├─ infra/               # Docker、Nginx、部署脚本
├─ docs/                # 计划、ADR、接口文档、运维手册
└─ .github/             # CI/CD、PR/Issue 模板
```

## 许可

[Apache-2.0](LICENSE)
