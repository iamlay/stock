const RETURN_ORIGIN = "https://stocklab.invalid";
const RETURN_ROUTES = new Set([
  "pricing",
  "account",
  "dashboard",
  "watchlist",
  "etf",
  "stocks",
  "strategies",
  "notifications",
]);

/** Accept only product pages on this site, preserving query parameters and hashes. */
export function safeReturnPath(value: unknown): string {
  if (typeof value !== "string" || value.length > 2048) return "/account";
  if (!value.startsWith("/") || value.startsWith("//") || /[\\\u0000-\u0020\u007f]/.test(value)) {
    return "/account";
  }
  try {
    const url = new URL(value, RETURN_ORIGIN);
    // Reject encoded separators, control characters and nested escaping in the path.
    // Query values may legitimately contain encoded URLs or Chinese search terms.
    const pathname = decodeURIComponent(url.pathname);
    if (/[\\%\u0000-\u0020\u007f]/.test(pathname) || pathname !== url.pathname) return "/account";
    if (
      url.origin !== RETURN_ORIGIN ||
      (pathname !== "/" && !RETURN_ROUTES.has(pathname.split("/")[1]))
    ) {
      return "/account";
    }
    // Restore strategy parameters without replaying a quota-consuming calculation.
    if (pathname.startsWith("/strategies/") && url.searchParams.has("run")) {
      url.searchParams.delete("run");
    }
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return "/account";
  }
}

export function withReturnPath(path: string, next: unknown): string {
  const url = new URL(path, RETURN_ORIGIN);
  url.searchParams.set("next", safeReturnPath(next));
  return `${url.pathname}${url.search}${url.hash}`;
}

export function currentReturnPath(): string {
  return typeof window === "undefined" ? "/account" : safeReturnPath(
    window.location.pathname + window.location.search + window.location.hash,
  );
}

/** A resumable selection, never an instruction to create an order automatically. */
export function checkoutResumePath(plan: string, payment: "alipay" | "wxpay", next: unknown): string {
  const query = new URLSearchParams({ plan, payment, next: safeReturnPath(next) });
  return safeReturnPath(`/pricing?${query.toString()}#checkout`);
}
