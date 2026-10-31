import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { PortfolioDividendAdd } from "@/components/portfolio-dividend-add";

export const metadata: Metadata = {
  title: "编辑分红记录",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};
export const dynamic = "force-dynamic";

export default async function DividendEditPage({
  params,
}: {
  params: Promise<{ code: string; receiptId: string }>;
}) {
  const { code, receiptId } = await params;
  if (!/^\d{6}$/.test(code) || !/^[0-9a-f-]{36}$/i.test(receiptId)) notFound();
  return <PortfolioDividendAdd code={code} receiptId={receiptId} />;
}
