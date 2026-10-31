import type { Metadata } from "next";

import { IncomeHome } from "@/components/income-home";

export const metadata: Metadata = {
  title: "收息首页",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};
export const dynamic = "force-dynamic";

export default function IncomePage() {
  return <IncomeHome />;
}
