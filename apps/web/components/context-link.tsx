"use client";

import { useEffect, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";

import { currentReturnPath, safeReturnPath, withReturnPath } from "@/lib/return-path";

/** Native navigation also preserves modifier-click/open-in-new-tab behavior. */
export function ContextLink({ href, children, className, returnPath }: {
  href: "/login" | "/pricing";
  children: ReactNode;
  className?: string;
  returnPath?: string;
}) {
  const pathname = usePathname();
  const [next, setNext] = useState<string | null>(null);
  const destination = () => returnPath === undefined ? currentReturnPath() : safeReturnPath(returnPath);
  useEffect(() => { setNext(returnPath === undefined ? currentReturnPath() : safeReturnPath(returnPath)); }, [pathname, returnPath]);
  // Do not offer a fallback destination before the browser context is available.
  if (next === null) return <span className={className} aria-disabled="true">{children}</span>;
  return <a href={withReturnPath(href, next)} className={className}
    onFocus={() => setNext(destination())}
    onMouseEnter={() => setNext(destination())}
    onClick={(event) => {
      // Read at activation so newly changed query parameters and hashes are included.
      event.currentTarget.href = withReturnPath(href, destination());
    }}>
    {children}
  </a>;
}
