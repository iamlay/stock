export type OrderStatus = {
  order_no: string;
  status: "pending" | "paid" | "delivered" | "refunded" | "closed" | "failed";
  product: string;
  amount: number;
  paid_at: string | null;
  delivered_at: string | null;
  plan_expires_at: string | null;
};

export function paymentReturnOrder(params: URLSearchParams): string | null {
  const orders = params.getAll("order");
  return orders.length === 1 && /^[A-Za-z0-9_-]{1,64}$/.test(orders[0]) ? orders[0] : null;
}

export function parseOrderStatus(value: unknown, expected: string): OrderStatus {
  const order = value as Partial<OrderStatus> | null;
  const date = (v: unknown) => v === null || (typeof v === "string" && Number.isFinite(Date.parse(v)));
  if (!order || order.order_no !== expected ||
      !["pending", "paid", "delivered", "refunded", "closed", "failed"].includes(order.status ?? "") ||
      typeof order.product !== "string" || typeof order.amount !== "number" ||
      !Number.isFinite(order.amount) || order.amount < 0 ||
      !date(order.paid_at) || !date(order.delivered_at) || !date(order.plan_expires_at) ||
      (order.status === "delivered" && (!order.paid_at || !order.delivered_at))) {
    throw new Error("订单响应暂无法确认，请稍后重试。");
  }
  return order as OrderStatus;
}

export type OrderPollResult =
  | { kind: "terminal"; order: OrderStatus }
  | { kind: "timeout" }
  | { kind: "cancelled" }
  | { kind: "error"; status?: number; message: string };

function pause(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const finish = () => { clearTimeout(timer); signal.removeEventListener("abort", finish); resolve(); };
    const timer = setTimeout(finish, ms);
    signal.addEventListener("abort", finish, { once: true });
    if (signal.aborted) finish();
  });
}

/** Serial, bounded polling: membership state and return URL flags are never payment evidence. */
export async function pollOrder(
  read: (signal: AbortSignal) => Promise<OrderStatus>,
  signal: AbortSignal,
  onPending: (order: OrderStatus) => void,
  { timeoutMs = 60_000, intervalMs = 2_000, requestTimeoutMs = 10_000 } = {},
): Promise<OrderPollResult> {
  const deadline = Date.now() + timeoutMs;
  while (!signal.aborted && Date.now() < deadline) {
    const request = new AbortController();
    const cancel = () => request.abort();
    signal.addEventListener("abort", cancel, { once: true });
    const timer = setTimeout(cancel, Math.min(requestTimeoutMs, deadline - Date.now()));
    try {
      const order = await read(request.signal);
      if (signal.aborted) return { kind: "cancelled" };
      if (Date.now() >= deadline) return { kind: "timeout" };
      if (!["pending", "paid"].includes(order.status)) return { kind: "terminal", order };
      onPending(order);
    } catch (error) {
      if (signal.aborted) return { kind: "cancelled" };
      if (Date.now() >= deadline) return { kind: "timeout" };
      const status = error && typeof error === "object" && "status" in error
        && typeof error.status === "number" ? error.status : undefined;
      return { kind: "error", status, message: request.signal.aborted
        ? "订单查询超时，请手动重试。" : error instanceof Error ? error.message : "订单查询失败，请稍后重试。" };
    } finally {
      clearTimeout(timer);
      signal.removeEventListener("abort", cancel);
    }
    await pause(Math.min(intervalMs, Math.max(0, deadline - Date.now())), signal);
  }
  return signal.aborted ? { kind: "cancelled" } : { kind: "timeout" };
}
