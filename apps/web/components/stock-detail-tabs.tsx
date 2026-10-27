"use client";

import { useEffect, useRef, useState } from "react";

const TABS = [
  { key: "overview", label: "概览" },
  { key: "dividend", label: "分红" },
  { key: "grid", label: "网格" },
  { key: "bollinger", label: "布林" },
  { key: "financial", label: "财务" },
] as const;
type Section = typeof TABS[number]["key"];
const isSection = (value: string | null): value is Section => TABS.some((tab) => tab.key === value);

export function StockDetailTabs() {
  const nav = useRef<HTMLElement>(null);
  const [active, setActive] = useState<Section>("overview");

  useEffect(() => {
    const element = nav.current;
    const page = element?.parentElement;
    if (!element || !page) return;
    const header = document.querySelector("header");
    let offset = 128;
    let frame = 0;
    let target: Section | null = null;

    function track() {
      frame = 0;
      let current: Section = "overview";
      for (const tab of TABS) {
        const section = document.getElementById(tab.key);
        if (section && section.getBoundingClientRect().top <= offset + 8) current = tab.key;
      }
      if (window.scrollY > 0 && window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2) current = "financial";
      setActive(current);
    }
    function onScroll() {
      if (!frame) frame = requestAnimationFrame(track);
    }
    function align() {
      if (target) document.getElementById(target)?.scrollIntoView({ block: "start", behavior: "instant" });
      onScroll();
    }
    function measure() {
      const top = header?.getBoundingClientRect().height ?? 56;
      element!.style.top = `${top}px`;
      offset = top + element!.getBoundingClientRect().height + 16;
      page!.style.setProperty("--stock-section-offset", `${offset}px`);
      align();
    }
    function locationTarget() {
      const hash = window.location.hash.slice(1);
      const values = new URLSearchParams(window.location.search).getAll("tab");
      const legacy = values.length === 1 ? values[0] : null;
      target = isSection(hash) ? hash : isSection(legacy) ? legacy : null;
      align();
    }
    // Keep deep links aligned while membership panels load, until the user takes over.
    function stopAligning() { target = null; }
    const resize = new ResizeObserver(measure);
    resize.observe(element);
    resize.observe(page);
    if (header) resize.observe(header);
    measure();
    locationTarget();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("hashchange", locationTarget);
    window.addEventListener("popstate", locationTarget);
    window.addEventListener("wheel", stopAligning, { passive: true });
    window.addEventListener("touchstart", stopAligning, { passive: true });
    window.addEventListener("keydown", stopAligning);
    window.addEventListener("pointerdown", stopAligning, { passive: true });
    return () => {
      resize.disconnect();
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("hashchange", locationTarget);
      window.removeEventListener("popstate", locationTarget);
      window.removeEventListener("wheel", stopAligning);
      window.removeEventListener("touchstart", stopAligning);
      window.removeEventListener("keydown", stopAligning);
      window.removeEventListener("pointerdown", stopAligning);
    };
  }, []);

  return (
    <nav ref={nav} aria-label="股票详情模块" className="sticky top-14 z-30 flex gap-1 overflow-x-auto border-b border-line bg-paper py-3 sm:gap-2">
      {TABS.map((tab) => (
        <a
          key={tab.key}
          href={`#${tab.key}`}
          aria-current={active === tab.key ? "location" : undefined}
          className={`shrink-0 rounded-sm px-3 py-1.5 text-sm transition-colors ${
            active === tab.key ? "bg-ink text-paper" : "text-ink-soft hover:bg-black/[0.04]"
          }`}
        >
          {tab.label}
        </a>
      ))}
    </nav>
  );
}
