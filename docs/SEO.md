# 个股 SEO

> 日期：2026-10-23
> 对应 V2-22
> 状态：最小 SEO 已上线

---

## 1. 已完成

### 个股详情元数据

`/stocks/[code]` 自动生成：

```text
title: 贵州茅台（600519）股息率与分红
description: 最新价、TTM 股息率、行业、分红/财务入口
keywords: 股票名、代码、股息率、分红、行业
canonical: https://stock.iamlay.com/stocks/600519
openGraph: title / description / url / type
twitter: summary card
robots: index, follow
```

无数据时：

```text
robots: noindex, nofollow
```

### 结构化数据

页面包含 JSON-LD：

```text
Corporation
  name
  tickerSymbol
  url

WebPage
  name
  description
  about

BreadcrumbList
  首页 → 高股息个股 → 行业 → 股票
```

### 面包屑

个股详情顶部：

```text
首页 / 高股息个股 / 食品饮料 / 贵州茅台
```

行业可点击，回到 `/stocks?industry=...`。

### Sitemap

```text
https://stock.iamlay.com/sitemap.xml
```

包含：

- 首页；
- 今日市场；
- ETF 列表、分类页与 100 只 ETF 详情；
- 个股列表、行业页与 5,000 只个股详情；
- 会员页；
- 隐私政策。

### ETF 详情

`/etf/[code]` 已支持全部 100 只 ETF，不再只预生成 20 只。

包含：

```text
title / description
canonical
openGraph
JSON-LD: FinancialProduct + WebPage + BreadcrumbList
分类面包屑
```

### 行业页

```text
/stocks/industry
/stocks/industry/[industry]
```

- 31 个申万一级行业入口；
- 行业涨跌幅与样本数；
- 行业个股按 TTM 股息率排序；
- 分页；
- canonical、JSON-LD、面包屑。

### ETF 分类页

```text
/etf/category
/etf/category/[category]
```

- 9 个 ETF 分类入口；
- 分类 ETF 列表；
- 分页；
- canonical、JSON-LD、面包屑。

### Robots

```text
https://stock.iamlay.com/robots.txt
```

禁止收录：

```text
/admin
/account
/notifications
/login
/forgot-password
/verify-email
/api/
```

并声明 sitemap。

### metadataBase

根布局已设置：

```text
https://stock.iamlay.com
```

保证相对 canonical/OG 正确。

---

## 2. 验证

```text
/sitemap.xml     ✅ 200，约 822 KB
/stocks/600519   ✅ 200
/etf/510300      ✅ 200
/etf/159201      ✅ 200
/etf/category/红利 ✅ 200
/stocks/industry/食品饮料 ✅ 200
JSON-LD          ✅
canonical        ✅
```

---

## 3. 注意

- 5,000 个页面属于长尾内容，收录需要时间；
- 空数据股票不要生成空页面，后续可加 `noindex`；
- 不要堆关键词；
- 不要写投资建议；
- 百度收录还要看备案、域名年龄和外链；
- sitemap 每次请求会读取 API，已设置 `revalidate=3600`。

---

## 4. 下一步

```text
1. ETF 详情 metadata
2. 行业页/分类页
3. 个股 FAQ 内容
4. 百度搜索资源平台提交 sitemap
5. 检查收录与索引量
```
