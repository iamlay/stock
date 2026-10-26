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
