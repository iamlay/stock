import type { Metadata } from "next";

export const metadata: Metadata = { title: "免责声明" };

export default function DisclaimerPage() {
  return (
    <div className="space-y-5 text-sm leading-7 text-ink-soft">
      <header>
        <p className="text-xs uppercase tracking-[0.18em] text-jade-deep">Disclaimer</p>
        <h1 className="mt-2 font-serif text-3xl text-ink">免责声明</h1>
        <p className="mt-2 text-xs text-muted">最后更新：2026-10-26</p>
      </header>

      <section className="space-y-3">
        <h2 className="font-serif text-xl text-ink">1. 不构成投资建议</h2>
        <p>
          StockLab 提供的是数据整理、指标计算和策略规则推演工具，不是证券投资咨询机构，
          不提供荐股、买卖点、代客理财或收益承诺。页面上的任何收益、回撤、估值分位、
          策略信号和文字说明，都不构成对你个人情况的投资建议。
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-xl text-ink">2. 数据来源与延迟</h2>
        <p>
          行情、份额、规模和估值数据来自第三方公开数据源，可能存在延迟、缺失、字段口径差异或接口变更。
          我们会做质量检查，但不保证数据绝对准确、完整或实时。页面展示的“最新”以数据管道实际更新时间为准。
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-xl text-ink">3. 回测的局限性</h2>
        <p>回测是在历史数据上按固定规则推演，不能代表未来收益。已知局限包括：</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>使用前复权价格，分红再投为近似处理；</li>
          <li>T 日收盘出信号、T+1 开盘成交，无法模拟盘中滑点；</li>
          <li>停牌、涨跌停、流动性和冲击成本只能近似；</li>
          <li>参数由用户选择，存在过拟合和幸存者偏差；</li>
          <li>未考虑税费、申赎限制、跟踪误差和基金费率差异。</li>
        </ul>
        <p>
          因此，回测收益、夏普、最大回撤等指标只能作为研究参考，不能作为实盘收益承诺。
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-xl text-ink">4. 不保证服务连续性</h2>
        <p>
          我们尽力保持服务稳定，但可能因维护、升级、网络、云服务、数据源或不可抗力中断。
          对因服务中断、数据延迟或功能调整造成的直接或间接损失，我们不承担赔偿责任。
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-xl text-ink">5. 风险自担</h2>
        <p>
          市场有风险，投资需谨慎。你应根据自身风险承受能力、资金安排和投资目标独立决策，
          并自行承担投资结果。任何时候都不要把本服务的内容当作“稳赚”或“保本”的依据。
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-xl text-ink">6. 第三方链接与平台</h2>
        <p>
          本服务可能包含第三方平台链接，会员付款由易支付通道承接。支付前请核对订单与收款信息并阅读相关规则。
          会员权益开通、到账异常和退款核查可联系我们协助处理，具体说明见用户协议。
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-xl text-ink">7. 联系方式</h2>
        <p>
          如对数据、回测口径或本声明有疑问，请联系：
          <a href="mailto:1187074543@qq.com" className="ml-1 text-jade-deep hover:underline">
            1187074543@qq.com
          </a>
        </p>
      </section>
    </div>
  );
}
