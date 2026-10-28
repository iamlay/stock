import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PortfolioPanel } from "@/components/portfolio-panel";

export const metadata: Metadata = {
  title: "持仓详情",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};
export const dynamic = "force-dynamic";
export default async function PortfolioDetailPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  if (!/^\d{6}$/.test(code)) notFound();
  return <PortfolioPanel selectedCode={code} />;
}
