# 备份、密钥轮换与数据库公网收口

> 对应 V2-07 / V2-08 / V2-09
> 更新：2026-10-21

---

## 1. 数据库备份（V2-07）

### 自动备份

工作流：

```text
.github/workflows/db-backup.yml
```

- 每天 03:00（北京时间）；
- `pg_dump` 自定义格式；
- 使用 `BACKUP_ENCRYPTION_KEY` 做 AES-256 加密；
- 上传 GitHub Actions Artifact，保留 14 天；
- 仓库是公开的，所以备份必须保持加密，不能上传明文。

需要配置的 Secret：

```text
STOCKLAB_DATABASE_URL     已有
BACKUP_ENCRYPTION_KEY     新增，至少 32 字节随机值
```

生成密钥：

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

把结果保存到密码管理器，并配置到 GitHub Secrets。

### 恢复演练

最省事的方式是 GitHub Actions：

```text
1. 打开成功的 DB Backup 运行，复制 URL 里的 run id
2. Actions → DB Restore Test → Run workflow
3. 填入 run id
4. 工作流会启动临时 postgres:18，恢复备份并输出行数
```

手动恢复：

```bash
STOCKLAB_DATABASE_URL='postgresql://...' \
BACKUP_ENCRYPTION_KEY='...' \
bash scripts/restore_backup.sh stocklab-2026-10-21.dump.enc
```

脚本会：

1. 要求输入 `RESTORE` 确认；
2. 解密；
3. `pg_restore --clean --if-exists`。

> 生产 PostgreSQL 是 18.x，本地 `pg_restore` 也必须是 18.x。
> 如果系统只有 16.x，先安装 PostgreSQL 18 客户端，
> 或使用 `/usr/lib/postgresql/18/bin/pg_restore`。

> 第一次演练不要直接对生产库执行。先建一个空测试库，恢复后检查：
> `instruments`、`users`、`stock_metrics`、`stock_dividends`、`market_daily` 行数。

### 备份验收

- [ ] `BACKUP_ENCRYPTION_KEY` 已配置；
- [ ] 手动跑一次 `DB Backup` 成功；
- [ ] Artifact 能下载；
- [ ] 在测试库恢复成功；
- [ ] 记录恢复耗时与行数；
- [ ] 确认 Railway 自身自动备份也已开启。

---

## 2. 密钥轮换（V2-08）

### 2.1 JWT / OTP

生成新密钥：

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

分别更新 Railway API 变量：

```text
STOCKLAB_JWT_SECRET
STOCKLAB_OTP_SECRET
```

重新部署 API 后，所有旧 JWT 自动失效。

可选：主动把所有用户 `token_version` 加一：

```bash
python -m app.cli rotate-tokens
```

### 2.2 数据库密码

1. Railway → PostgreSQL → Settings → Credentials；
2. 轮换密码；
3. 更新 API 的 `STOCKLAB_DATABASE_URL`（如果使用引用则自动跟随）；
4. 更新 GitHub Secret `STOCKLAB_DATABASE_URL`；
5. 重新部署 API；
6. 确认 `/healthz` 和 `/api/v1/data/status` 正常。

### 2.3 邮件服务

- Resend / Brevo API Key 重新生成；
- 更新 Railway API 的 `STOCKLAB_RESEND_API_KEY` / `STOCKLAB_BREVO_API_KEY`；
- 确认 SPF/DKIM 仍然有效；
- 发一封测试邮件。

### 2.4 安全检查命令

```bash
python -m app.cli security-check
```

检查：

```text
STOCKLAB_ENV
STOCKLAB_AUTH_DEV_MODE
JWT/OTP 是否默认值或过短
CORS 是否包含 localhost
FRONTEND_URL 是否 https
数据库是否本地默认地址
邮件是否配置
```

返回非零表示存在 fail。

### 2.5 轮换验收

- [ ] JWT/OTP 已换；
- [ ] 旧登录态全部失效；
- [ ] DB 密码已换，API 正常；
- [ ] GitHub Actions 仍能连库；
- [ ] 邮件能发；
- [ ] `security-check` 无 FAIL。

---

## 3. 数据库公网收口（V2-09）

### 重要依赖

当前 GitHub Actions 的 ETL、备份、质量任务使用：

```text
STOCKLAB_DATABASE_URL = Railway DATABASE_PUBLIC_URL
```

**直接关闭 Public Networking 会让所有 GitHub Actions 任务失败。**

正确顺序：

```text
1. 把 ETL/备份/质量任务迁到 Railway 内部服务
2. 使用 ${{Postgres.DATABASE_URL}} 内网连接
3. 验证任务成功
4. 再关闭 PostgreSQL Public Networking
5. 删除 GitHub 的 public DB secret，改用 Railway 内部执行
```

### 临时方案

如果暂时不迁移：

- 保留 Public Networking；
- 使用强密码；
- 限制访问来源（Railway 当前能力有限）；
- 只把 public URL 放在 GitHub Secrets，不写进代码；
- 定期轮换 DB 密码。

### 关闭步骤（迁移完成后）

1. Railway → PostgreSQL → Settings → Networking；
2. 关闭 **Public Networking**；
3. 确认 API 使用：

```text
STOCKLAB_DATABASE_URL=${{Postgres.DATABASE_URL}}
```

4. 确认所有 ETL 在 Railway 内网运行；
5. 删除 GitHub 的 public DB secret；
6. 重新跑一次日报/个股任务。

### 验收

- [ ] API 正常；
- [ ] 每日 ETL 正常；
- [ ] 备份正常；
- [ ] 质量检查正常；
- [ ] 公网端口无法连接；
- [ ] 代码与文档中无 public DB URL。

---

## 4. 当前建议执行顺序

```text
1. 配置 BACKUP_ENCRYPTION_KEY
2. 手动跑一次 DB Backup
3. 在测试库恢复
4. 轮换 JWT / OTP
5. 轮换 DB 密码
6. 轮换邮件 Key
7. security-check
8. 迁移 ETL 到 Railway
9. 关闭 DB Public Networking
```
