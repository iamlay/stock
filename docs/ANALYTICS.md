# Vercel Analytics 接入说明

> 日期：2026-10-22
> 当前 Web 部署：Vercel
> 统计方案：Vercel Web Analytics
> 状态：已接入并启用

---

## 1. 代码

Web 已安装：

```text
@vercel/analytics
```

根布局：

```tsx
import { Analytics } from "@vercel/analytics/next";

<body>
  {children}
  <Analytics />
</body>
```

验证：

```text
next typecheck  ✅
next build      ✅
```

---

## 2. 线上配置

Vercel 项目：

```text
iamlay/stock
```

必需环境变量：

```text
API_BASE_URL=https://stock-production-c535.up.railway.app
NEXT_PUBLIC_API_BASE_URL=https://stock-production-c535.up.railway.app
```

Railway API 的 CORS 必须包含：

```text
https://stock.iamlay.com
```

Vercel 项目 → Analytics → Web Analytics：

```text
Enabled
```

---

## 3. 验证

### 页面

打开：

```text
https://stock.iamlay.com
```

### Vercel 后台

Vercel → 项目 → Analytics → Real-time。

应看到：

- 访问量；
- 页面路径；
- 来源；
- 设备/浏览器；
- 国家/地区。

### 浏览器 Network

应出现：

```text
/_vercel/insights/script.js
```

或 Vercel Analytics 相关请求。

---

## 4. 能统计什么

Vercel Web Analytics 提供：

- Page Views；
- Visitors；
- Top Pages；
- Referrers；
- Devices；
- Browsers；
- Countries；
- Real-time。

不提供：

- 用户注册/登录转化；
- 自选/回测行为；
- 站内漏斗；
- 用户级路径。

如果需要这些，需要：

- 自定义事件；
- 或 PostHog/Umami 等产品分析。

---

## 5. 自定义事件（后续）

如果要做“注册成功、添加自选、完成回测”漏斗，可以加：

```ts
import { track } from "@vercel/analytics";

track("add_watchlist", { code: "510300" });
```

建议事件：

```text
signup_success
login_success
add_watchlist
run_backtest
open_stock_detail
```

注意不要发送邮箱、手机号等个人身份信息。

---

## 6. 隐私

隐私政策建议补充：

```text
我们会使用 Vercel Analytics 统计页面访问量、来源、设备类型等聚合信息，
用于改进产品体验，不用于识别个人身份。
```

如果增加自定义事件，也要说明事件类型与用途。

---

## 7. 验收

- [x] `@vercel/analytics` 已安装；
- [x] 根布局已渲染 `<Analytics />`；
- [x] Web 部署在 Vercel；
- [x] Web Analytics 已开启；
- [ ] Real-time 能看到访问；
- [ ] 隐私政策已补充；
- [ ] 需要时增加自定义事件。

---

## 8. 故障排查

### 没有数据

1. Vercel 项目是否开启 Web Analytics；
2. 是否访问的是 Vercel 部署域名；
3. 浏览器是否拦截脚本；
4. 是否有广告拦截插件；
5. 刚开启需要几分钟。

### 有访问但某些页面没有

- 确认页面走的是同一个 Vercel 项目；
- 确认没有被重定向到 Railway Web；
- 检查 `stock.iamlay.com` DNS 指向 Vercel。

### 数据延迟

Vercel Analytics 通常几分钟内更新；Real-time 更快。
