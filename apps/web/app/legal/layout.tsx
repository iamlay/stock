import type { ReactNode } from "react";
import Link from "next/link";

import { SiteFooter, SiteHeader } from "@/components/chrome";

const legalNav = [
  { href: "/legal/terms", label: "用户协议" },
  { href: "/legal/privacy", label: "隐私政策" },
  { href: "/legal/disclaimer", label: "免责声明" },
];

export default function LegalLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <SiteHeader />
      <main className="mx-auto max-w-4xl px-6 py-12">
        <div className="flex flex-wrap gap-2 border-b border-line pb-4">
          {legalNav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-sm border border-line bg-surface px-3 py-1.5 text-xs text-ink-soft hover:border-ink hover:text-ink"
            >
              {item.label}
            </Link>
          ))}
        </div>
        <article className="mt-8">{children}</article>
        <p className="mt-10 border-t border-line pt-4 text-xs leading-6 text-muted">
          生效日期：2026-10-20 · 如对本页面有疑问，请联系{" "}
          <a href="mailto:1187074543@qq.com" className="text-jade-deep hover:underline">
            1187074543@qq.com
          </a>
          。
        </p>
      </main>
      <SiteFooter />
    </div>
  );
}
