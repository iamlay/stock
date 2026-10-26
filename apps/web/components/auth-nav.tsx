"use client";

import { ContextLink } from "@/components/context-link";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { fetchMe, getToken, type Me } from "@/lib/auth";

type State = "loading" | "guest" | "user";

export function AuthNavActions({
  variant = "app",
}: {
  variant?: "app" | "site";
}) {
  const pathname = usePathname();
  const [state, setState] = useState<State>("loading");
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    let active = true;
    if (!getToken()) {
      setState("guest");
      setMe(null);
      return;
    }
    setState("loading");
    fetchMe()
      .then((profile) => {
        if (!active) return;
        setMe(profile);
        setState("user");
      })
      .catch(() => {
        if (!active) return;
        setMe(null);
        setState("guest");
      });
    return () => {
      active = false;
    };
  }, [pathname]);

  useEffect(() => {
    function onStorage(event: StorageEvent) {
      if (event.key === "stocklab.token") {
        setState("loading");
        if (!getToken()) {
          setMe(null);
          setState("guest");
        }
      }
    }
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const base =
    variant === "site"
      ? "hidden sm:inline-flex rounded-sm border border-line px-3.5 py-2 text-sm text-ink-soft transition-colors hover:border-ink hover:text-ink"
      : "inline-flex rounded-sm border border-line px-2.5 py-1.5 text-xs text-ink-soft transition-colors hover:border-ink hover:text-ink";

  if (state === "loading") {
    return (
      <span
        className={
          variant === "site"
            ? "hidden text-sm text-muted sm:inline"
            : "text-xs text-muted"
        }
      >
        账号…
      </span>
    );
  }

  if (state === "user") {
    return (
      <Link href="/account" className={base} title={me?.email ?? me?.phone ?? "个人中心"}>
        {variant === "site" ? "个人中心" : "个人中心"}
      </Link>
    );
  }

  return (
    <ContextLink href="/login" className={base}>
      登录
    </ContextLink>
  );
}
