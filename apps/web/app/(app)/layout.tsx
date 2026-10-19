import type { ReactNode } from "react";
import Link from "next/link";

import { AppNav, Logo } from "@/components/chrome";

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-paper">
      <header className="sticky top-0 z-40 border-b border-line bg-paper/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-4 sm:gap-4 sm:px-6">
          <div className="shrink-0">
            <Logo />
          </div>
          <div className="ml-1 hidden h-5 w-px shrink-0 bg-line sm:block" />
          <AppNav />
          <div className="ml-auto flex shrink-0 items-center gap-2 sm:gap-3">
            <span className="hidden text-xs text-muted lg:block">演示环境 · 示例数据</span>
            <Link
              href="/account"
              className="hidden rounded-sm border border-line px-3 py-1.5 text-xs text-ink-soft hover:border-ink hover:text-ink sm:block"
            >
              个人中心
            </Link>
            <Link
              href="/login"
              className="hidden rounded-sm bg-ink px-3 py-1.5 text-xs font-medium text-paper hover:bg-jade-deep sm:block"
            >
              登录
            </Link>          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">{children}</main>

      <footer className="mx-auto max-w-6xl px-4 pb-10 sm:px-6">
        <p className="border-t border-line pt-5 text-xs leading-6 text-muted">
          行情与规模来自本地数据管道；板块与策略仍为示例。历史回测不代表未来收益，不构成投资建议。
        </p>
      </footer>
    </div>
  );
}
