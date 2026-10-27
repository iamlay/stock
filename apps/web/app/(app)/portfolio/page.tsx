import type { Metadata } from "next";
import { PortfolioPanel } from "@/components/portfolio-panel";

export const metadata: Metadata = {
  title: "私人账本", robots: { index: false, follow: false },
  referrer: "no-referrer",
};
export const dynamic = "force-dynamic";

export default function PortfolioPage() { return <PortfolioPanel />; }
