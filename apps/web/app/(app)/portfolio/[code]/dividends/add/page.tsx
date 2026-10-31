import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { PortfolioDividendAdd } from "@/components/portfolio-dividend-add";

export const metadata: Metadata = {
  title: "添加分红记录",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};
export const dynamic = "force-dynamic";

export default async function DividendAddPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  if (!/^\d{6}$/.test(code)) notFound();
  return <PortfolioDividendAdd code={code} />;
}
