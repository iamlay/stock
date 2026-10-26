"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { taskDestination } from "@/lib/task-context";

export function ReturnToTask({ confirmed = false }: { confirmed?: boolean }) {
  const params = useSearchParams();
  // The payment panel exposes the task only after this specific order is delivered.
  if (!confirmed && params.getAll("payment").includes("return")) return null;
  const task = taskDestination(new URLSearchParams(params.toString()));
  if (!task) return null;
  return <div className="rounded-sm border border-line bg-surface p-4 text-sm">
    <Link href={task.href} className="text-jade-deep underline">{task.label} →</Link>
    <p className="mt-2 text-xs text-muted">仅恢复页面和参数；添加自选、保存提醒、支付和运行回测需要你再次确认。</p>
  </div>;
}
