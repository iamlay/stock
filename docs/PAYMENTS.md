# 在线支付接入（易支付 / ezfpy）

> 2026-10-26 更新（V2-37）：标准会员当前 **¥9.99/30 天，不自动扣费**。在售商品与权益唯一来源为 `apps/api/app/api/v1/plans.py`；前端从 `/api/v1/plans` 读取，订单复用同一商品定义。邀请码只控制注册，会员兑换码用于权益交付；试用与回测导出尚未交付，不列入在售权益。

## 1. 通道

使用页面跳转支付：

```text
POST https://www.ezfpy.cn/submit.php
```

支付方式：

```text
alipay  支付宝
wxpay   微信支付
```

签名：

```text
参数按 ASCII 升序
排除 sign / sign_type / 空值
拼接 key=value&key=value
末尾拼接商户密钥
MD5 小写
```

## 2. 环境变量

```bash
STOCKLAB_EZFPY_BASE_URL=https://www.ezfpy.cn
STOCKLAB_EZFPY_PID=你的商户ID
STOCKLAB_EZFPY_KEY=你的商户密钥
STOCKLAB_EZFPY_NOTIFY_URL=https://stock-production-c535.up.railway.app/api/v1/billing/notify
STOCKLAB_EZFPY_RETURN_URL=https://stock.iamlay.com/account?payment=return
STOCKLAB_FRONTEND_URL=https://stock.iamlay.com
```

说明：

- `EZFPY_KEY` 只能放在 API 环境变量，不能出现在 Web 构建变量中；
- `NOTIFY_URL` 必须是公网 HTTPS；
- 未配置 `PID` / `KEY` 时，`POST /api/v1/billing/checkout` 返回 503；
- `RETURN_URL` 可省略，默认使用 `FRONTEND_URL/account?payment=return`。

## 3. 前端流程

```text
/pricing
→ 选择套餐
→ 支付宝 / 微信
→ POST /api/v1/billing/checkout
→ 返回支付网关地址 + 签名字段
→ 浏览器自动提交表单
→ 易支付收银台
→ return_url 返回个人中心
```

支付成功后：

```text
易支付 notify_url
→ 验签
→ 校验 pid / 金额 / 订单状态
→ 激活会员
→ 订单 delivered
→ 返回纯文本 success
```

## 4. 接口

### 创建订单

```http
POST /api/v1/billing/checkout
Authorization: Bearer <token>
Content-Type: application/json

{
  "plan_id": "standard-monthly",
  "payment_type": "alipay"
}
```

返回：

```json
{
  "order_no": "SL20261025213000ABC123",
  "amount": 9.99,
  "pay_url": "https://www.ezfpy.cn/submit.php",
  "method": "POST",
  "fields": {
    "pid": "1000",
    "type": "alipay",
    "out_trade_no": "SL...",
    "notify_url": "https://.../api/v1/billing/notify",
    "return_url": "https://stock.iamlay.com/account?payment=return",
    "name": "StockLab 标准会员",
    "money": "9.99",
    "sign_type": "MD5",
    "sign": "..."
  }
}
```

### 异步通知

```http
GET|POST /api/v1/billing/notify
```

成功返回：

```text
success
```

失败返回：

```text
fail
```

### 订单查询

```http
GET /api/v1/billing/order/{order_no}
Authorization: Bearer <token>
```

## 5. 安全约束

- 服务端生成订单号与金额，浏览器不能改价；
- 回调必须验签；
- 校验 `pid`；
- 校验 `trade_status=TRADE_SUCCESS`；
- 校验金额与订单金额一致；
- 只有订单所属用户可以查询；
- 已 delivered 的订单重复回调直接返回 success，保证幂等；
- 不保存银行卡、支付密码等信息；
- 支付密钥不得写入日志、前端 bundle 或 Git。

## 6. 数据

订单表：

```text
payment_orders
```

状态：

```text
pending
delivered
refunded
```

支付成功后：

```text
payment_orders.status = delivered
payment_orders.paid_at = now
payment_orders.external_order_id = trade_no
users.plan = member
users.plan_expires_at += duration_days
```

有效会员续费从当前有效期继续累加；到期后需主动购买或兑换，不会自动扣费。

前端在跳转收银台前比较订单金额与当前展示价格；不一致则提示刷新确认，不自动按新价付款。套餐接口不可用时不展示旧价格或购买入口。

## 7. 退款

当前未实现在线退款 API 自动调用。

退款需要：

1. 在易支付商户后台发起；
2. 后台登记订单状态为 refunded；
3. 视情况扣减会员时长。

不建议直接在数据库改状态，避免账实不一致。

## 8. 测试

```bash
python -m pytest apps/api/tests/test_billing.py -q
```

覆盖：

- 签名排序；
- 创建订单；
- 回调验签；
- 会员激活；
- 幂等重复回调。

## 9. 注意

- 易支付是第三方聚合通道，商户资质、结算、发票与合规由商户自行确认；
- 生产环境必须使用 HTTPS；
- 回调地址必须能从公网访问；
- 不要在前端暴露 `EZFPY_KEY`；
- 支付成功后以服务端回调为准，return_url 仅用于页面跳转。
