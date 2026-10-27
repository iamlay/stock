# V2-49：分红事件版本、日期及来源

> 2026-10-27：本地开发与验证完成，待推送/部署；未操作生产数据库。
> 任务状态唯一来源：[主计划第 20 节](DEVELOPMENT_PLAN.md#20-高股息深度用户持仓收息与分红质量专项2026-10-27)。技术决策见 [ADR-0009](adr/0009-dividend-event-versions.md)。

## 1. 本次交付

- 事件有独立 UUID，日期、金额或方案更正不改变已确认关联的事件 ID；同报告期可明确创建多个独立事件。
- 事件版本保留登记日、除息日、派息日、报告/公告日期、阶段、精确金额、来源 URL、原始 JSON、核对说明和修订人。
- 来源观察保留取消、零分红、金额未知和日期未知等记录。相同核心内容重复同步不会重复入队；股价、距除息日天数等动态字段不产生伪修订。
- 新来源观察进入管理员待核对队列，不擅自关联或覆盖版本；管理员可新建、追加修订或忽略，核对结果和审计原子提交。
- 旧研究接口及股票详情响应不变；旧数据可有界、幂等回填为未核验快照。不存在“自动把自选变成持仓”或“到日自动到账”。

V2-48 的访谈、完整公告核验、时效、历史覆盖和来源使用条件仍待补证；本任务不改变其状态。这里实现字段和人工核对能力，不表示上游已能自动提供所有日期。

## 2. 迁移和上线顺序

新增 Alembic revision：`c8d4e6f29013`，前置为 `a8f3c2d6e915`。只创建三张表及约束/索引，不改旧表、不自动回填。

1. 确认备份可恢复，先发布包含迁移的 API，等待启动迁移成功；再运行依赖新表的分红 ETL。现有 Dockerfile 启动命令已有 `alembic upgrade head`，仍需检查实际部署日志及数据库 head，不能只看构建成功。
2. API 容器工作目录为 `/app`，迁移命令如下。若平台覆盖了启动命令，先在同一环境执行迁移再启动新任务；多副本迁移要串行执行。

```bash
# API 镜像 /app 内，使用该环境已配置的数据库连接
alembic current
alembic upgrade head
alembic current

# 本地仓库根目录的等价命令，必须明确连接目标环境
python -m alembic -c apps/api/alembic.ini upgrade head
```

确认 head 为 `c8d4e6f29013`。不新增环境变量，不改变五分钟行情或定时 workflows。现有 Actions 分红任务会先迁移再运行 ETL，但 API 部署与任务顺序仍应核查。

3. 先对少量旧记录 dry-run，再显式 apply。工具不全自动扫描，避免上线时意外大批量写入。

```bash
# 仓库根目录或 /app 内均可（Python 环境需要能导入 app 与 etl）
python -m etl.dividend_events_backfill --limit 100
python -m etl.dividend_events_backfill --limit 100 --apply

# 使用上一批返回的 last_id 继续；下面的 100 仅为示例，须替换为真实返回值
python -m etl.dividend_events_backfill --after-id 100 --limit 100
python -m etl.dividend_events_backfill --after-id 100 --limit 100 --apply
```

返回 `scanned`、`candidates`、`created`、`last_id`、`applied`。dry-run 的 created 为 0；apply 重跑不重复生成。按实际 last_id 继续，直到 scanned 为 0；`limit` 支持 1–2000。每批核对事件数、旧 ID 映射、金额与未知日期，不能只用总数判定身份已正确。

4. 通过现有分红同步入口收集新观察，再由管理员核对。原始观察和旧研究记录来自同一次抓取，不额外发起重复网络查询。研究解析仍保留原语义，完整生命周期核对使用新观察表。
5. 生产走查新接口、旧股票详情、自选和原股息率，核对 API 当前版本与数据库 head。迁移和本地测试不等于生产验收完成。

## 3. 接口契约

以下路径均在 `/api/v1` 下。

| 接口 | 权限与用途 |
|---|---|
| `GET /stocks/{code}/dividend-events` | 公开当前事件版本，股票必须有效且未排除；page_size 最大 100 |
| `GET /stocks/{code}/dividend-events/{id}/versions` | 公开历史版本，校验事件归属股票，分页 |
| `GET /admin/stocks/dividend-observations` | 管理员队列；state 为 pending/applied/ignored，可按 code 筛选 |
| `GET /admin/stocks/dividend-observations/{id}` | 管理员查看原始数据、来源及核对记录 |
| `POST /admin/stocks/dividend-observations/{id}/review` | 管理员明确创建、修订或忽略来源观察 |

新事件接口金额为十进制字符串，未知金额/日期为 null；旧详情金额仍按原数值契约返回。公开结果不暴露管理员 ID、原始 JSON 或内部核对说明；管理员响应 `Cache-Control: private, no-store`。

当前版本列表包含 `pending_observations`：有新证据尚未核对时，已发布版本不能被误解成“所有最新来源变化均已处理”。`origin=legacy_snapshot`、`evidence_status=legacy_unverified` 表示旧数据快照；`reviewed` 仅表示管理员做过该次证据核对，不能等同于个人应收或实际到账。

`automatic_entitlement_allowed`、`automatic_receipt_allowed` 始终为 false，后续收息计算不得只凭 stage=implemented 跳过准入条件。未知阶段保留原文；来源首次披露、抓取时间和版本创建时间分别展示。

## 4. 管理员人工核对

先查看原始观察，再查询该股票事件和版本，确认它是新一轮分红还是已有方案更正。不要仅凭同一报告期/同一方案文字决定合并。

新建示例：

```json
{
  "action": "create",
  "expected_revision": 0,
  "note": "已核对实施公告及分红轮次，补录现金红利发放日",
  "patch": {
    "payment_date": "2026-07-10",
    "announcement_url": "https://example.com/issuer-announcement.pdf"
  }
}
```

上述 URL 为占位示例，须使用真实核对公告。原始来源字段不被覆盖，人工修改进入版本字段及审计。派息日必须有公告 URL；服务只保存链接、不代为下载，禁止非 HTTP(S) 或含用户名/密码的 URL。支持的 patch 只有报告日、登记日、除息日、派息日、每股金额、公告链接与规范阶段；额外字段拒绝。

关联到已有事件并追加修订：

```json
{
  "action": "revise",
  "event_id": "替换为目标事件的真实UUID",
  "expected_revision": 1,
  "note": "已核对同一分红方案的更正公告，确认本次关联",
  "patch": {}
}
```

`expected_revision` 取当前查询值。并发更新返回 409，须重新查看版本及证据。新观察比当前版本公告日期更旧或缺日期时，默认拒绝覆盖；只有说明原因并显式设置 `allow_older_evidence=true` 才允许追加，旧版本始终保留。修订不会默认继承旧版本的手工派息日，需重新提供已核对证据。

忽略重复或不适用观察：

```json
{
  "action": "ignore",
  "expected_revision": 0,
  "note": "已人工复核，此来源记录不属于本次可处理事件"
}
```

同一观察重复提交完全相同决策会返回原版本，不新增事件、修订或审计；改用不同决策返回 409。ignored 不能附带目标事件或修改字段。所有新核对的说明至少 8 字符，记录管理员和时间；当前没有修改/删除历史版本或跨股票关联的公开入口。

## 5. 兼容、回退和后续消费

旧表仍用于既有研究结果，新事件版本用于人工核对及未来收息功能；V2-49 不把未经验证的新来源强行切入原股息率，也不把两个来源的行相加。旧表后续更新不会修改已有事件快照，需要核对新来源观察后明确追加版本。自动关联与研究投影切换应在证据补齐后另行验收。

上线故障先暂停受影响的分红任务并回退兼容应用；新表保留，旧数据未被迁移修改。**不要对已有真实事件修订的生产数据库直接执行 destructive downgrade**，它会删除新事件及审计关联。降级到 `a8f3c2d6e915` 再升级只用于隔离测试，生产应备份保全后前滚修复。

后续 V2-52 必须从已验证的新事件/版本消费，并记录计算时引用的版本。stage、日期存在或人工核对一个字段，都不能代替持仓历史完整性、公司行动及 V2-48 总门槛。

## 6. 验证证据

- 本机独立临时 PostgreSQL：从空库迁移至旧 head，插入旧分红样本，再升级至新 head；旧行逐字段一致。
- 真实旧数据样本的 dry-run、apply、重复 apply、降级、再次升级及再次回填通过，回填事件 UUID 稳定。
- PostgreSQL 并发测试覆盖同一观察采集、同一审核重试、竞争追加版本和重复旧数据回填；只有一次事件/审计，不丢版本。
- API 全套 **288 项测试通过**，包括本任务 39 项功能/接口测试及 5 项真实 PostgreSQL 测试；没有跳过 PostgreSQL 测试。40 条 V2-48 原始样本在本地离线保存且重复采集不增条目。
- 全仓 Python 静态检查通过。新表迁移不依赖线上数据库；临时服务器验证结束后已停止。
- 本次未改 Web，旧详情 API 回归通过；没有执行真实支付或生成个人账本/应收。

复现：

```bash
python -m pytest apps/api/tests/test_dividend_events.py -q
# 指向可丢弃测试 PostgreSQL，测试自行使用唯一 schema 并清理
python -m pytest apps/api/tests/test_dividend_events_postgres.py -q
python -m ruff check apps/api etl
```

第二条命令需要已配置 `STOCKLAB_TEST_POSTGRES_URL`；未配置会明确 skip，不能将该情况下的结果记录为真实数据库验证通过。CI 已有独立 PostgreSQL 服务和相应环境变量，新测试会随原测试命令执行。
