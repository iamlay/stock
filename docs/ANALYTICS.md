# Vercel Analytics 接入说明

> 日期：2026-10-22
> 当前 Web 部署：Railway
> 统计方案：Vercel Web Analytics

---

## 1. 已完成的代码

Web 已安装：

```text
@vercel/analytics
```

根布局已加入：

```tsx
import { Analytics } from "@vercel/analytics/next";

<body>
  {children}
  <Analytics />
</body>
```

`typecheck` 和 `next build` 均通过。

---

## 2. 重要限制

**Vercel Analytics 只在 Vercel 部署上采集数据。**

当前 Web 在 Railway，Vercel 的统计脚本依赖：

```text
/_vercel/insights/script.js
```

Railway 不提供这个路径，所以：

- 页面不会报错；
- 但 Vercel 后台不会出现数据；
- 本地 `next start` 也不会看到统计脚本。

如果继续用 Railway，需要换成：

- Umami；
- Plausible；
- PostHog；
- 自建统计。

---

## 3. 方案 A：把 Web 迁到 Vercel

这是使用 Vercel Analytics 的前提。

### 3.1 导入项目

Vercel → Add New Project → `iamlay/stock`。

推荐配置：

| 项 | 值 |
|---|---|
| Framework | Next.js |
| Root Directory | 仓库根目录 |
| Install Command | `pnpm install --frozen-lockfile` |
| Build Command | `pnpm --filter @stocklab/web build` |
| Output Directory | 默认 |

### 3.2 环境变量

```text
API_BASE_URL=https://stock-production-c535.up.railway.app
NEXT_PUBLIC_API_BASE_URL=https://stock-production-c535.up.railway.app
```

### 3.3 域名

Vercel → Domains：

```text
stock.iamlay.com
```

把 DNS 从 Railway 指向 Vercel。

### 3.4 CORS

Railway API 的 `STOCKLAB_CORS_ORIGINS` 增加：

```text
https://stock.iamlay.com
```

如果先用 Vercel 预览域名，也加上：

```text
https://<project>.vercel.app
```

### 3.5 开启 Analytics

Vercel 项目 → Analytics → Enable Web Analytics。

部署后：

- 打开页面；
- Vercel Analytics → Real-time；
- 应看到访问记录。

### 3.6 验证脚本

浏览器 Network 中应出现：

```text
/_vercel/insights/script.js
```

或页面源码中存在 Vercel Analytics 相关脚本。

---

## 4. 方案 B：继续用 Railway

如果暂时不迁移 Web：

- `@vercel/analytics` 保留不会影响页面；
- 但不会产生统计数据；
- 建议改用 Umami/Plausible/PostHog。

不要为了统计强行把页面代理到 Vercel，维护成本更高。

---

## 5. 隐私与合规

Vercel Web Analytics 默认不采集个人身份信息，但仍建议在隐私政策中补充：

```text
我们会使用 Vercel Analytics 统计页面访问量、来源、设备类型等聚合信息，
用于改进产品体验，不用于识别个人身份。
```

如果启用 Speed Insights，也要补充性能数据说明。

---

## 6. 验收

- [ ] Web 已部署到 Vercel；
- [ ] `stock.iamlay.com` 指向 Vercel；
- [ ] API CORS 允许 Vercel 域名；
- [ ] Vercel Analytics 已开启；
- [ ] Real-time 能看到访问；
- [ ] 隐私政策已补充；
- [ ] 页面无 JS 报错。

---

## 7. 当前状态

```text
代码接入：✅
Railway 上采集：❌ 不支持
Vercel 上采集：待迁移后启用
```
