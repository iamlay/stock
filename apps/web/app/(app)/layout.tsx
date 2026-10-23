import type { ReactNode } from "react";

import { AppNav, Logo } from "@/components/chrome";
import { AuthNavActions } from "@/components/auth-nav";

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
            <span className="hidden text-xs text-muted lg:block">ETF 投研工作台</span>
            <AuthNavActions />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">{children}</main>

      <footer className="mx-auto max-w-6xl px-4 pb-10 sm:px-6">
        <p className="border-t border-line pt-5 text-xs leading-6 text-muted">
          行情与规模来自本地数据管道；分类热力按重点 ETF 分类等权；市场温度为估算。历史回测不代表未来收益，不构成投资建议。
        </p>
      </footer>
    </div>
  );
}
