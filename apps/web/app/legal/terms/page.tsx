import type { Metadata } from "next";

import { MembershipSummary } from "@/components/membership-summary";

export const metadata: Metadata = { title: "用户协议" };

export default function TermsPage() {
  return (
    <div className="space-y-5 text-sm leading-7 text-ink-soft">
      <header>
        <p className="text-xs uppercase tracking-[0.18em] text-jade-deep">Terms of Service</p>
        <h1 className="mt-2 font-serif text-3xl text-ink">用户协议</h1>
        <p className="mt-2 text-xs text-muted">最后更新：2026-10-26</p>
      </header>

      <section className="space-y-3">
        <h2 className="font-serif text-xl text-ink">1. 服务说明</h2>
        <p>
          StockLab（以下称“本服务”）是一个面向个人投资者的 ETF
          数据、估值、策略回测与研究工具。本服务提供历史行情、指标计算、策略规则推演和回测结果展示，
          <strong className="text-ink">不提供证券投资咨询、代客理财、荐股或交易执行服务</strong>。
        </p>
        <p>
          本服务覆盖 ETF 与 A 股个股研究数据，不提供期货、期权、外汇交易。所有回测均为历史规则推演，
          不代表未来收益，也不构成任何投资建议。
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-xl text-ink">2. 账号注册与安全</h2>
        <p>
          你可以使用邮箱和密码注册账号。注册后需要完成邮箱验证才能登录。手机号为可选信息，
          用于账号绑定、手机号邀请码或后续短信登录。
        </p>
        <p>
          你应提供真实、有效的联系方式，并妥善保管账号密码。因你主动泄露密码、共用账号或未及时更新安全信息
          造成的损失，由你自行承担。发现账号异常时，请立即通过文末邮箱联系我们。
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-xl text-ink">3. 使用规范</h2>
        <p>你同意不实施以下行为：</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>使用自动化程序批量注册、刷接口、爬取数据或干扰服务稳定；</li>
          <li>绕过会员限制、回测次数限制、邀请码或兑换码校验；</li>
          <li>将账号、兑换码、邀请码出售、出租或转让给他人；</li>
          <li>复制、转售、再分发本服务的数据、指标或策略代码；</li>
          <li>利用本服务从事任何违反法律法规的活动。</li>
        </ul>
        <p>
          对违反上述规范、影响其他用户或服务安全的账号，我们有权限制功能、暂停或终止服务。
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-xl text-ink">4. 会员、兑换码与费用</h2>
        <p>
          会员支持支付宝 / 微信支付，由易支付通道承接收款；也可使用会员兑换码开通。
          一次购买对应套餐时长，不自动扣费。当前套餐价格与权益如下，实际购买前请核对定价页。
        </p>
        <MembershipSummary />
        <p>
          支付确认后自动开通会员；有效会员再次购买或兑换时叠加时长，到期后需主动续费。
          邀请码仅用于注册准入，不会自动开通会员。会员兑换码需在个人中心兑换，并受其有效期、次数及账号绑定限制。
        </p>
        <p>
          已验证邮箱且符合资格的账号可在个人中心主动领取一次 7 天体验，领取后按连续 7×24 小时计时。
          注册与验证邮箱不会自动启动体验，体验无需付款且不会自动扣费。试用回测沿用免费账号计算额度，
          到期后保留数据与设置并暂停高级功能；试用期间购买会员，付费时长从交付时刻起计算，不叠加剩余试用时间。
        </p>
        <p>
          如付款后未到账，请提供订单号联系我们核查。退款与发票的适用条件请在购买前联系确认；
          当前退款需人工核查订单、处理款项及对应权益，不提供自动退款或未经确认的退款时效承诺。
        </p>
        <p>
          本服务可能调整免费额度、会员权益或价格，调整前会通过页面公告等合理方式提示。
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-xl text-ink">5. 知识产权</h2>
        <p>
          本服务的页面设计、文字、图表、策略规则、代码和数据组织方式归运营者或相关权利人所有。
          未经书面许可，不得复制、修改、传播或用于商业用途。
        </p>
        <p>
          行情、估值和份额数据来自第三方数据源，相关权利归原数据提供方所有；本服务仅在约定范围内使用。
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-xl text-ink">6. 服务变更、中断与终止</h2>
        <p>
          我们可能因维护、升级、数据源调整、不可抗力或合规要求，暂停或变更部分功能。
          我们会尽力提前提示，但不对因服务中断造成的间接损失承担责任。
        </p>
        <p>
          你可以随时停止使用本服务。对长期未验证、违规或存在安全风险的账号，我们有权清理或限制。
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-xl text-ink">7. 免责与责任限制</h2>
        <p>
          本服务按“现状”提供。我们不保证数据绝对准确、完整、及时，也不保证任何策略、指标或回测结果
          适用于你的具体情况。你应独立判断并自行承担投资决策及后果。
        </p>
        <p>
          在适用法律允许的范围内，我们对因使用或无法使用本服务产生的间接、附带、惩罚性损失不承担责任。
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-xl text-ink">8. 协议更新与联系方式</h2>
        <p>
          我们可能更新本协议。更新后在页面公布即生效；若你继续使用，视为接受更新后的协议。
        </p>
        <p>
          联系邮箱：
          <a href="mailto:hi@stocklab.dev" className="text-jade-deep hover:underline">
            hi@stocklab.dev
          </a>
        </p>
      </section>
    </div>
  );
}
