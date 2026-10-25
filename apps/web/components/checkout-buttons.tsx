"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { createCheckout, getToken } from "@/lib/auth";

export function CheckoutButtons({ planId }: { planId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState<"alipay" | "wxpay" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function pay(paymentType: "alipay" | "wxpay") {
    setError(null);
    if (!getToken()) {
      router.push("/login?next=/pricing");
      return;
    }
    setBusy(paymentType);
    try {
      const checkout = await createCheckout(planId, paymentType);
      const form = document.createElement("form");
      form.method = checkout.method || "POST";
      form.action = checkout.pay_url;
      form.style.display = "none";
      for (const [name, value] of Object.entries(checkout.fields)) {
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = name;
        input.value = value;
        form.appendChild(input);
      }
      document.body.appendChild(form);
      form.submit();
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建支付订单失败");
      setBusy(null);
    }
  }

  return (
    <div className="mt-8 space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={() => pay("alipay")}
          disabled={busy !== null}
          className="rounded-sm bg-ink px-4 py-2.5 text-sm font-medium text-paper transition-colors hover:bg-jade-deep disabled:opacity-60"
        >
          {busy === "alipay" ? "跳转中…" : "支付宝支付"}
        </button>
        <button
          type="button"
          onClick={() => pay("wxpay")}
          disabled={busy !== null}
          className="rounded-sm border border-line bg-surface px-4 py-2.5 text-sm font-medium text-ink transition-colors hover:border-ink disabled:opacity-60"
        >
          {busy === "wxpay" ? "跳转中…" : "微信支付"}
        </button>
      </div>
      <p className="text-[11px] leading-5 text-muted">
        支付成功后会员自动到账；如未到账，请回到个人中心刷新。
      </p>
      {error ? <p className="text-xs text-loss">{error}</p> : null}
    </div>
  );
}
