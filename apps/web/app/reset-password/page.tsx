import type { Metadata } from "next";

import { SiteFooter, SiteHeader } from "@/components/chrome";
import { ResetPasswordForm } from "@/components/reset-password-form";

export const metadata: Metadata = { title: "重置密码" };

export default async function ResetPasswordPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>;
}) {
  const params = await searchParams;
  return (
    <div className="min-h-screen">
      <SiteHeader />
      <main className="mx-auto max-w-6xl px-6 py-14">
        <ResetPasswordForm token={params.token ?? ""} />
      </main>
      <SiteFooter />
    </div>
  );
}
