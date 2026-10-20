import type { Metadata } from "next";

import { SiteFooter, SiteHeader } from "@/components/chrome";
import { ForgotPasswordForm } from "@/components/forgot-password-form";

export const metadata: Metadata = { title: "忘记密码" };

export default function ForgotPasswordPage() {
  return (
    <div className="min-h-screen">
      <SiteHeader />
      <main className="mx-auto max-w-6xl px-6 py-14">
        <ForgotPasswordForm />
      </main>
      <SiteFooter />
    </div>
  );
}
