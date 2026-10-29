import type { Metadata } from "next";

import { PortfolioIncome } from "@/components/portfolio-income";

export const metadata: Metadata = {
  title: "收息账本",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};
export const dynamic = "force-dynamic";

export default function PortfolioIncomePage() {
  return <PortfolioIncome />;
}
