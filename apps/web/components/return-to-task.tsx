"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { safeReturnPath } from "@/lib/return-path";

export function ReturnToTask() {
  const [next, setNext] = useState<string | null>(null);
  useEffect(() => {
    const values = new URLSearchParams(window.location.search).getAll("next");
    if (values.length !== 1) return;
    const path = safeReturnPath(values[0]);
    if (path !== "/account") setNext(path);
  }, []);
  if (!next) return null;
  return <div className="rounded-sm border border-line bg-surface p-4 text-sm">
    <Link href={next} className="text-jade-deep underline">返回原页面继续研究 →</Link>
    <p className="mt-2 text-xs text-muted">仅返回页面；支付、添加自选和运行回测等操作需要你再次确认。</p>
  </div>;
}
