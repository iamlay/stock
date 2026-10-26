"use client";

import { useEffect, useState } from "react";
import { ContextLink } from "@/components/context-link";
import { MembershipSummary } from "@/components/membership-summary";
import { fetchMe, getToken, type Me } from "@/lib/auth";

const COPY = {
  watchlist: { title: "继续跟踪更多标的", description: "会员可添加更多股票与 ETF 自选，集中观察行情与股息。到期后已有自选保留；升级返回后，请再次点击加入自选。" },
  alerts: { title: "让提醒替你关注目标", description: "网格提醒关注目标股息率对应的价格，低位共振提醒辅助筛选关注机会。涨跌与除息提醒继续免费；提醒不代表收益保证。" },
  history: { title: "回看策略，比较研究结果", description: "会员可查看已保存的回测记录及收益曲线，回顾不同标的和参数的表现。免费回测额度保持不变，历史表现不代表未来收益。" },
};

export function UpgradePrompt({ scene, profile, returnPath }: {
  scene: keyof typeof COPY; profile?: Me | null; returnPath?: string;
}) {
  const [fetched, setFetched] = useState<Me | null>(null);
  useEffect(() => {
    if (profile !== undefined || !getToken()) return;
    let active = true;
    fetchMe().then((me) => { if (active) setFetched(me); }).catch(() => undefined);
    return () => { active = false; };
  }, [profile]);
  const me = profile ?? fetched;
  const expired = me?.plan === "member" && !me.entitlements.capabilities.advanced_data;
  const copy = COPY[scene];
  return <aside className="my-3 w-full max-w-xl rounded-sm border border-line bg-surface p-4 text-left" aria-label={copy.title}>
    <h3 className="text-sm font-medium text-ink">{expired ? "恢复会员，继续原来的研究" : copy.title}</h3>
    <p className="mt-2 text-xs leading-6 text-muted">{copy.description}</p>
    <MembershipSummary compact />
    <ContextLink href="/pricing" returnPath={returnPath} className="mt-3 inline-block rounded-sm bg-ink px-3 py-2 text-sm text-paper">
      {expired ? "续费并返回继续" : "查看套餐并继续当前任务"}
    </ContextLink>
  </aside>;
}
