"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const nav = [
  { href: "/dashboard", label: "今日市场", short: "市场" },
  { href: "/etf", label: "ETF 数据", short: "ETF" },
  { href: "/stocks", label: "高股息", short: "股息" },
  { href: "/watchlist", label: "我的自选", short: "自选" },
  { href: "/strategies", label: "策略实验室", short: "策略" },
  { href: "/pricing", label: "会员", short: "会员" },
];

export function AppNav() {
  const pathname = usePathname();

  return (
    <nav className="flex min-w-0 items-center gap-1 overflow-x-auto">
      {nav.map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={[
              "whitespace-nowrap rounded-sm px-2.5 py-2 text-sm transition-colors sm:px-3",
              active
                ? "bg-jade-soft font-medium text-jade-deep"
                : "text-ink-soft hover:bg-black/[0.04] hover:text-ink",
            ].join(" ")}
          >
            <span className="sm:hidden">{item.short}</span>
            <span className="hidden sm:inline">{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-2.5 focus-ring">
      <span className="flex h-8 w-8 items-center justify-center rounded-sm bg-ink text-sm font-semibold text-paper">
        稳
      </span>
      {!compact ? (
        <span className="text-[15px] font-semibold tracking-tight text-ink">
          Stock<span className="text-jade">Lab</span>
        </span>
      ) : null}
    </Link>
  );
}

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-paper/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-6 px-6">
        <Logo />
        <nav className="hidden items-center gap-7 text-sm text-ink-soft md:flex">
          <Link href="/dashboard" className="hover:text-ink">
            今日市场
          </Link>
          <Link href="/etf" className="hover:text-ink">
            ETF 数据
          </Link>
          <Link href="/stocks" className="hover:text-ink">
            高股息
          </Link>
          <Link href="/strategies" className="hover:text-ink">
            策略实验室
          </Link>
          <Link href="/pricing" className="hover:text-ink">
            会员
          </Link>
        </nav>
        <div className="flex items-center gap-3">
          <Link
            href="/login"
            className="hidden rounded-sm border border-line px-3.5 py-2 text-sm text-ink-soft transition-colors hover:border-ink hover:text-ink sm:block"
          >
            登录
          </Link>
          <Link
            href="/dashboard"
            className="rounded-sm bg-ink px-3.5 py-2 text-sm font-medium text-paper transition-colors hover:bg-jade-deep"
          >
            进入工作台
          </Link>
        </div>
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t border-line bg-paper">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
          <div className="max-w-md">
            <Logo />
            <p className="mt-3 text-sm leading-6 text-muted">
              面向稳健型投资者的 ETF 投研工具。数据、估值与策略规则全部公开口径，不构成投资建议。
            </p>
          </div>
          <div className="flex gap-10 text-sm">
            <div className="space-y-2">
              <p className="font-medium text-ink">产品</p>
              <Link href="/dashboard" className="block text-muted hover:text-ink">
                今日市场
              </Link>
              <Link href="/etf" className="block text-muted hover:text-ink">
                ETF 数据
              </Link>
              <Link href="/strategies" className="block text-muted hover:text-ink">
                策略实验室
              </Link>
            </div>
            <div className="space-y-2">
              <p className="font-medium text-ink">关于</p>
              <Link href="/pricing" className="block text-muted hover:text-ink">
                会员与兑换
              </Link>
              <Link href="/login" className="block text-muted hover:text-ink">
                登录
              </Link>
              <a href="mailto:hi@stocklab.dev" className="block text-muted hover:text-ink">
                联系我们
              </a>
            </div>
            <div className="space-y-2">
              <p className="font-medium text-ink">法律</p>
              <Link href="/legal/terms" className="block text-muted hover:text-ink">
                用户协议
              </Link>
              <Link href="/legal/privacy" className="block text-muted hover:text-ink">
                隐私政策
              </Link>
              <Link href="/legal/disclaimer" className="block text-muted hover:text-ink">
                免责声明
              </Link>
            </div>
          </div>
        </div>
        <div className="mt-8 border-t border-line pt-5 text-xs leading-6 text-muted">
          <p>市场有风险，投资需谨慎。所有回测均为历史规则推演，不代表未来收益，不构成任何投资建议。</p>
          <p className="mt-1">© {new Date().getFullYear()} StockLab · 历史回测不代表未来收益。</p>
        </div>
      </div>
    </footer>
  );
}
