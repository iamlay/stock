import type { Metadata } from "next";

import { SiteFooter, SiteHeader } from "@/components/chrome";
import { VerifyEmailSentPanel } from "@/components/verify-email-sent-panel";

export const metadata: Metadata = { title: "验证邮件已发送" };

export default async function VerifyEmailSentPage({
  searchParams,
}: {
  searchParams: Promise<{ email?: string; next?: string | string[] }>;
}) {
  const params = await searchParams;
  return (
    <div className="min-h-screen">
      <SiteHeader />
      <main className="mx-auto max-w-6xl px-6 py-14">
        <VerifyEmailSentPanel email={params.email ?? ""} next={params.next} />
      </main>
      <SiteFooter />
    </div>
  );
}
