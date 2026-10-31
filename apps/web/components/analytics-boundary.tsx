"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

export function AnalyticsBoundary({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  if (
    pathname === "/portfolio" ||
    pathname?.startsWith("/portfolio/") ||
    pathname === "/income" ||
    pathname?.startsWith("/income/")
  ) return null;
  return children;
}
