"use client";

import { useEffect, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";

import { currentReturnPath, withReturnPath } from "@/lib/return-path";

/** Native navigation also preserves modifier-click/open-in-new-tab behavior. */
export function ContextLink({ href, children, className }: {
  href: "/login" | "/pricing";
  children: ReactNode;
  className?: string;
}) {
  const pathname = usePathname();
  const [next, setNext] = useState<string | null>(null);
  useEffect(() => { setNext(currentReturnPath()); }, [pathname]);
  // Do not offer a fallback destination before the browser context is available.
  if (next === null) return <span className={className} aria-disabled="true">{children}</span>;
  return <a href={withReturnPath(href, next)} className={className}
    onFocus={() => setNext(currentReturnPath())}
    onMouseEnter={() => setNext(currentReturnPath())}
    onClick={(event) => {
      // Read at activation so newly changed query parameters and hashes are included.
      event.currentTarget.href = withReturnPath(href, currentReturnPath());
    }}>
    {children}
  </a>;
}
