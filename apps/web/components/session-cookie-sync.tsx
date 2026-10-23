"use client";

import { useEffect } from "react";

import { getToken } from "@/lib/auth";

export function SessionCookieSync() {
  useEffect(() => {
    const token = getToken();
    if (!token) return;
    void fetch("/api/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    }).catch(() => undefined);
  }, []);

  return null;
}
