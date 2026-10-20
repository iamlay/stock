import type { Metadata } from "next";

import { SiteFooter, SiteHeader } from "@/components/chrome";
import { VerifyEmailPanel } from "@/components/verify-email-panel";

export const metadata: Metadata = { title: "验证邮箱" };

export default async function VerifyEmailPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>;
}) {
  const params = await searchParams;
  return (
    <div className="min-h-screen">
      <SiteHeader />
      <main className="mx-auto max-w-6xl px-6 py-14">
        <VerifyEmailPanel token={params.token ?? ""} />
      </main>
      <SiteFooter />
    </div>
  );
}
