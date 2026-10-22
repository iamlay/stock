import type { Metadata } from "next";

export const metadata: Metadata = { title: "隐私政策" };

export default function PrivacyPage() {
  return (
    <div className="space-y-5 text-sm leading-7 text-ink-soft">
      <header>
        <p className="text-xs uppercase tracking-[0.18em] text-jade-deep">Privacy Policy</p>
        <h1 className="mt-2 font-serif text-3xl text-ink">隐私政策</h1>
        <p className="mt-2 text-xs text-muted">最后更新：2026-10-20</p>
      </header>

      <section className="space-y-3">
        <h2 className="font-serif text-xl text-ink">1. 适用范围</h2>
        <p>
          本政策适用于 StockLab 网站及其 API。我们尽量只收集提供服务所必需的信息，
          不收集与投研工具无关的敏感个人信息。
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-xl text-ink">2. 我们收集的信息</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong className="text-ink">账号信息</strong>：邮箱、可选手机号、密码哈希；
          </li>
          <li>
            <strong className="text-ink">登录与安全信息</strong>：登录时间、IP 地址、请求日志；
          </li>
          <li>
            <strong className="text-ink">使用信息</strong>：回测标的、策略、参数、回测结果、自选 ETF；
          </li>
          <li>
            <strong className="text-ink">交易与会员信息</strong>：兑换码、订单号、会员状态、到期时间；
          </li>
          <li>
            <strong className="text-ink">邮件信息</strong>：验证邮件和密码重置邮件的发送记录。
          </li>
        </ul>
        <p>
          我们不会收集你的身份证号、银行卡号、证券账户或持仓信息，也不要求你上传任何证件。
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-xl text-ink">3. 使用目的</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>注册、登录、邮箱验证和密码重置；</li>
          <li>保存回测历史、自选和会员状态；</li>
          <li>校验兑换码、邀请码和订单归属；</li>
          <li>防止刷接口、批量注册和其他滥用行为；</li>
          <li>排查故障、改进产品和保障服务安全。</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-xl text-ink">4. Cookie 与本地存储</h2>
        <p>
          我们使用浏览器 <code className="rounded bg-black/5 px-1">localStorage</code> 保存登录
          token，用于保持登录状态。该 token 不包含密码，关闭或清理浏览器数据后需要重新登录。
        </p>
        <p>
          当前不使用广告 Cookie，也不接入第三方广告追踪。我们使用 Vercel Analytics
          和百度统计了解页面访问量、来源、设备类型等聚合信息，用于改进产品体验，
          不用于识别个人身份。
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-xl text-ink">5. 共享与委托处理</h2>
        <p>为提供服务，我们可能委托以下类型的服务商处理必要数据：</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>云主机与数据库：部署 API、Web 和 PostgreSQL；</li>
          <li>邮件服务：发送验证邮件和密码重置邮件；</li>
          <li>域名、CDN 和安全防护服务。</li>
        </ul>
        <p>
          我们不会出售你的个人信息，也不会将你的邮箱、手机号用于与投研服务无关的营销。
          除法律法规要求或保护服务安全所必需外，不会向无关第三方披露。
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-xl text-ink">6. 存储与保留</h2>
        <p>
          账号和会员数据在账号存续期间保留；回测历史、订单和兑换码记录按业务需要保留。
          长期未验证账号、异常账号或不再需要的日志，可能被清理或匿名化。
        </p>
        <p>
          数据主要存储在当前部署区域的云数据库中。跨境传输时，我们会遵守适用法律的要求。
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-xl text-ink">7. 安全措施</h2>
        <p>
          密码使用 scrypt 加盐哈希存储；登录使用短期 JWT；邮箱验证和密码重置使用限时签名链接；
          关键后台操作记录审计日志。尽管如此，互联网服务不存在绝对安全，请使用独立密码并保护邮箱安全。
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-xl text-ink">8. 你的权利</h2>
        <p>
          你可以通过账号页面查看和修改可编辑信息，也可以发邮件申请访问、更正或删除账号数据。
          为保护账号安全，我们可能需要先验证你的身份。
        </p>
        <p>
          删除账号后，部分订单、兑换码或审计记录可能因法律、财务或安全需要继续保留，
          我们会在合理期限后清理或匿名化。
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-xl text-ink">9. 未成年人</h2>
        <p>
          本服务面向具备完全民事行为能力的投资者。未成年人不应注册或使用本服务。
          如发现未成年人注册，我们会限制或删除相关账号。
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-xl text-ink">10. 政策更新与联系方式</h2>
        <p>
          我们可能更新本政策。重大变更会在页面提示。继续使用本服务视为接受更新后的政策。
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
