"use client";

import { AdvancedPreview, type PreviewFeature } from "@/components/advanced-preview";
import { ContextLink } from "@/components/context-link";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";

import { MembershipSummary } from "@/components/membership-summary";
import { fetchMe, getToken, type Me } from "@/lib/auth";

type GateState = "loading" | "member" | "guest" | "free";

export function MemberGate({
  feature,
  children,
}: {
  feature: string;
  children: ReactNode;
}) {
  const [state, setState] = useState<GateState>("loading");
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    if (!getToken()) {
      setState("guest");
      return;
    }
    fetchMe()
      .then((user) => {
        setMe(user);
        setState(user.entitlements?.capabilities.advanced_data ? "member" : "free");
      })
      .catch(() => setState("guest"));
  }, []);

  if (state === "loading") {
    return (
      <div className="card p-8 text-center text-sm text-muted">
        正在确认会员权限…
      </div>
    );
  }

  if (state === "member") return <>{children}</>;

  const previewFeature = ({ "股息网格": "grid", "股息布林": "bollinger", "股息财务": "financial" } as Record<string, PreviewFeature>)[feature];

  return (
    <div className="card p-4 text-center sm:p-8">
      {previewFeature ? <AdvancedPreview feature={previewFeature} authenticated={state === "free"} /> : null}
      <p className="text-xs font-medium uppercase tracking-[0.18em] text-jade">
        完整研究工具
      </p>
      <h2 className="mt-2 font-serif text-2xl text-ink">解锁完整{feature}</h2>
      <p className="mx-auto mt-3 max-w-lg text-sm leading-6 text-muted">
        {state === "guest"
          ? "登录并开通会员后可查看。免费账号仍可使用 ETF、个股列表、基础详情和价格/除息提醒。"
          : `当前账号没有有效会员权益。开通会员后可使用${feature}，具体权益如下。`}
      </p>
      <MembershipSummary />
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        {state === "guest" ? (
          <ContextLink
            href="/login"
            className="rounded-sm bg-ink px-4 py-2 text-sm font-medium text-paper"
          >
            登录
          </ContextLink>
        ) : (
          <Link
            href="/account"
            className="rounded-sm border border-line bg-surface px-4 py-2 text-sm text-ink-soft hover:border-ink"
          >
            我的账号
          </Link>
        )}
        {me?.entitlements?.trial_eligible ? <Link
          href="/account#trial"
          className="rounded-sm border border-jade px-4 py-2 text-sm text-jade-deep"
        >查看 7 天体验</Link> : null}
        <ContextLink
          href="/pricing"
          className="rounded-sm bg-ink px-4 py-2 text-sm font-medium text-paper"
        >
          查看会员权益
        </ContextLink>
      </div>
      {me?.plan_expires_at ? (
        <p className="mt-4 text-xs text-muted">
          当前会员到期：{me.plan_expires_at.slice(0, 10)}
        </p>
      ) : null}
    </div>
  );
}
