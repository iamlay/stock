import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { PortfolioDividendRecords } from "@/components/portfolio-dividend-records";

export const metadata: Metadata = {
  title: "分红记录",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};
export const dynamic = "force-dynamic";

export default async function DividendRecordsPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  if (!/^\d{6}$/.test(code)) notFound();
  return <PortfolioDividendRecords code={code} />;
}
