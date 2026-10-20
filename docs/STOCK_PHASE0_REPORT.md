# 个股模块 Phase 0 数据源验证报告

> 日期：2026-10-20
> 范围：全市场 A 股列表、分红、单股日线、股息率计算
> 结论：**可以进入 Phase 1，但必须先补行业数据源，并处理 Eastmoney 限流。**

---

## 1. 验证内容

| 项 | 验证方式 | 结果 |
|---|---|---|
| 全市场股票列表 | Eastmoney clist / 新浪 hs_a | ⚠️ Eastmoney 断连，Sina 兜底可用 |
| 股票快照 | 价格、市值、PE、PB、ST | ✅ Sina 可用 |
| 行业字段 | Eastmoney f100 | ❌ Sina 无行业，当前全为“未分类” |
| 分红数据 | Eastmoney RPT_SHAREBONUS_DET | ✅ 可用 |
| 单股日线 | 腾讯 fqkline | ✅ 可用，但最新只到 10-19 |
| 股息率计算 | TTM / 最近年度 | ✅ 样本结果合理 |

---

## 2. 全市场列表

### Eastmoney

```text
https://push2.eastmoney.com/api/qt/clist/get
```

- 第一次 PowerShell 请求成功，返回 `total=5562`；
- 随后 Python / curl 连续请求被断开：
  `RemoteDisconnected: Remote end closed connection without response`；
- 判断为 IP/频率限制或 TLS 指纹拦截，不适合作为稳定主源。

### 新浪兜底

```text
https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData
```

实测：

```text
total=5217
ST=193
industry=1（全部“未分类”）
```

字段：

- `symbol` / `code` / `name`
- `trade` 最新价
- `changepercent` 涨跌
- `per` PE
- `pb`
- `mktcap` 总市值（万元）
- `nmc` 流通市值（万元）

问题：

- `node=hs_a` 会混入北交所 `bj` 代码，需要过滤；
- 没有行业字段；
- 5,217 与 Eastmoney 的 5,562 有差异，需要 Phase 1 对账（北交所、退市、停牌、基金等）。

---

## 3. 分红数据

Eastmoney：

```text
https://datacenter-web.eastmoney.com/api/data/v1/get
reportName=RPT_SHAREBONUS_DET
```

- 按 `SECURITY_CODE` 查询，分页返回；
- 只保留 `ASSIGN_PROGRESS` 含“实施/分配”且有 `EX_DIVIDEND_DATE` 的记录；
- `PRETAX_BONUS_RMB` 是**每 10 股**税前分红，必须 `/10`；
- 字段包含 `REPORT_DATE`、`EX_DIVIDEND_DATE`、`IMPL_PLAN_PROFILE`；
- 可识别“特别分红”。

样本：

| 股票 | 分红记录数 | 最近除息日 | TTM 股息率 | 年度股息率 |
|---|---|---|---|---|
| 600519 贵州茅台 | 27 | 2026-06-26 | 3.90% | 3.90% |
| 601398 工商银行 | 23 | 2026-05-13 | 3.62% | 3.62% |
| 600036 招商银行 | 25 | 2026-07-10 | 4.74% | 4.74% |
| 601088 中国神华 | 21 | 2026-07-13 | 3.92% | 3.92% |
| 600028 中国石化 | 50 | 2026-09-30 | 3.98% | 1.93% |

结论：

- TTM 和年度口径会因中期分红产生明显差异，**默认 TTM 是合理的**；
- 必须排除未来除息日，不能把“已公告未除息”计入 TTM；
- 分红记录需要去重 `(code, ex_date, plan)`。

---

## 4. 单股日线

使用腾讯：

```text
https://web.ifzq.gtimg.cn/appstock/app/fqkline/get
```

样本：

```text
600519: 432 行，2025-01-02 → 2026-10-19，close=1324.97
601398: 432 行，2025-01-02 → 2026-10-19，close=8.6
```

问题：

- 最新交易日只到 10-19，10-20 收盘数据尚未更新；
- `amount` 为 0，不能用于成交额分析；
- 单股按需拉取可行，但不适合预拉全市场 10 年。

结论：

- K 线只用于详情页图表；
- 全市场排序不依赖 K 线；
- Phase 1 需要加“最新日期不足”质量检查。

---

## 5. 风险结论

| 风险 | 结论 |
|---|---|
| Eastmoney 列表接口 | 不稳定，必须做 Sina 兜底 |
| 行业字段 | 当前缺失，Phase 1 阻塞项 |
| 分红接口 | 可用，但字段单位是每 10 股 |
| 腾讯日线 | 可用，但有 1 天延迟、成交额为 0 |
| 全市场数量 | 5,217 / 5,562 不一致，需要对账 |
| 用户乱加代码 | 需要 6 位校验、A 股过滤、限流 |

---

## 6. Phase 1 必须补的

1. **行业数据源**：Eastmoney F10、申万行业映射或新浪行业节点；
2. **全市场对账**：确定 5,217 与 5,562 的差异，明确是否含北交所/退市/基金；
3. **列表源容错**：Eastmoney 优先、Sina 兜底、失败重试；
4. **分红去重和未来日期过滤**；
5. **单股 K 线按需缓存**，不要预拉全市场；
6. **每日全市场任务限速和断点续跑**。

---

## 7. 建议

- 主源：Eastmoney（可用时）；
- 兜底：Sina；
- 分红：Eastmoney；
- K 线：Tencent 按需；
- 行业：Phase 1 单独补，未补齐前行业筛选先隐藏或显示“未分类”；
- 首版先灰度 500 只，验证 1 周后再扩全市场。

Phase 0 结论：**数据链路可行，但不能直接全量上线；行业与对账是 Phase 1 的硬前置。**
