import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center px-6">
      <div className="max-w-md text-center">
        <p className="tnum text-xs text-muted">404</p>
        <h1 className="mt-2 font-serif text-3xl text-ink">这一页还没有数据</h1>
        <p className="mt-3 text-sm leading-6 text-muted">
          链接可能已失效，或该标的尚未纳入覆盖范围。回到工作台继续查看。
        </p>
        <div className="mt-6 flex justify-center gap-3">
          <Link
            href="/dashboard"
            className="rounded-sm bg-ink px-4 py-2.5 text-sm font-medium text-paper hover:bg-jade-deep"
          >
            回到工作台
          </Link>
          <Link
            href="/etf"
            className="rounded-sm border border-line bg-surface px-4 py-2.5 text-sm text-ink hover:border-ink"
          >
            浏览 ETF
          </Link>
        </div>
      </div>
    </div>
  );
}
