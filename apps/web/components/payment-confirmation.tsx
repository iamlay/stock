"use client";

import Link from "next/link";
import { ReturnToTask } from "@/components/return-to-task";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { fetchMe, fetchPaymentOrder, type Me } from "@/lib/auth";
import { paymentReturnOrder, pollOrder, type OrderPollResult, type OrderStatus } from "@/lib/order-status";
import { currentReturnPath, withReturnPath } from "@/lib/return-path";

type View = OrderPollResult | { kind: "checking"; order?: OrderStatus } | { kind: "invalid" };

export function PaymentConfirmation({ onProfile }: { onProfile: (profile: Me) => void }) {
  const query = useSearchParams().toString();
  const [attempt, setAttempt] = useState(0);
  const [storedView, setView] = useState<View>({ kind: "checking" });
  const [viewQuery, setViewQuery] = useState(query);
  const view: View = viewQuery === query ? storedView : { kind: "checking" };
  const [profileError, setProfileError] = useState(false);
  const [loginHref, setLoginHref] = useState("/login");
  const params = new URLSearchParams(query);
  const returning = params.getAll("payment").includes("return");
  const orderNo = paymentReturnOrder(params);

  useEffect(() => {
    const values = new URLSearchParams(query);
    if (!values.getAll("payment").includes("return")) return;
    setLoginHref(withReturnPath("/login", currentReturnPath()));
    setProfileError(false);
    setViewQuery(query);
    const order = paymentReturnOrder(values);
    if (!order || values.getAll("payment").length !== 1) {
      setView({ kind: "invalid" });
      return;
    }
    const controller = new AbortController();
    setView({ kind: "checking" });
    void pollOrder(
      (signal) => fetchPaymentOrder(order, signal), controller.signal,
      (pending) => setView({ kind: "checking", order: pending }),
    ).then(async (result) => {
      if (controller.signal.aborted) return;
      setView(result);
      if (result.kind === "terminal" && result.order.status === "delivered") {
        try {
          const profile = await fetchMe();
          if (!controller.signal.aborted) onProfile(profile);
        } catch {
          if (!controller.signal.aborted) setProfileError(true);
        }
      }
    });
    return () => controller.abort();
  }, [query, attempt, onProfile]);

  if (!returning) return null;
  const order = view.kind === "terminal" || view.kind === "checking" ? view.order : undefined;
  const delivered = view.kind === "terminal" && order?.status === "delivered";
  const needsLogin = view.kind === "error" && view.status === 401;
  let message = "正在查询本订单，最多自动确认 60 秒…";
  if (view.kind === "invalid") message = "回跳地址缺少有效订单号，无法确认本次支付。请保留支付凭证与订单号，联系支持核查。";
  if (view.kind === "checking" && order) message = order.status === "paid"
    ? "本订单已确认付款，正在等待会员权益交付…"
    : "尚未确认本订单付款与交付，正在等待支付回调。请勿重复付款。";
  if (view.kind === "timeout") message = "暂未确认本订单交付，自动查询已暂停。这不代表支付失败；请稍后手动重试，不要重复付款。";
  if (view.kind === "error") message = needsLogin ? "登录已过期，请重新登录后查询本订单。"
    : view.status === 404 || view.status === 403 ? "未找到当前账号可查询的在线订单，请核对订单号和登录账号。"
    : view.status === 429 ? "订单查询过于频繁，已暂停自动查询，请稍后重试。" : view.message;
  if (view.kind === "terminal") message = delivered ? "本订单支付已确认，会员权益已交付。"
    : order?.status === "refunded" ? "本订单已标记退款，请联系支持核实退款进度。"
    : "本订单已关闭或失败。如已扣款，请保留支付凭证联系支持核查。";

  return <section aria-labelledby="payment-confirmation-title" className="rounded-sm border border-line bg-surface p-5">
    <h2 id="payment-confirmation-title" className="text-base font-medium text-ink">本次支付确认</h2>
    {orderNo ? <p className="mt-2 break-all text-xs text-muted">订单号：{orderNo}</p> : null}
    {order ? <p className="mt-2 text-xs text-muted">订单金额：¥{order.amount.toFixed(2)}</p> : null}
    <p role="status" aria-live="polite" className={`mt-3 text-sm ${delivered ? "text-jade-deep" : "text-ink-soft"}`}>{message}</p>
    {delivered ? <ReturnToTask confirmed /> : null}
    {profileError && viewQuery === query ? <p role="alert" className="mt-2 text-sm text-muted">订单已交付，但会员资料暂未刷新，请重试刷新。</p> : null}
    <div className="mt-3 flex flex-wrap gap-4 text-sm">
      {needsLogin ? <Link href={loginHref} className="text-jade-deep underline">重新登录并查询</Link> : null}
      {(!needsLogin && (view.kind === "timeout" || view.kind === "error" || profileError)) ?
        <button type="button" onClick={() => setAttempt((value) => value + 1)} className="text-jade-deep underline">
          {profileError ? "刷新会员资料" : "重新查询订单"}
        </button> : null}
      <Link href="/legal/terms" className="text-muted underline">查看支持联系方式</Link>
    </div>
  </section>;
}
