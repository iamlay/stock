import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "StockLab · 稳健 ETF 投研台",
    template: "%s · StockLab",
  },
  description:
    "面向稳健型投资者的 ETF 投研工具：市场温度、估值分位、ETF 数据与可复现的策略回测。",
  keywords: ["ETF", "红利低波", "估值分位", "策略回测", "稳健投资"],
  openGraph: {
    title: "StockLab · 稳健 ETF 投研台",
    description: "把回撤放在第一位：ETF 数据、估值与可复现的策略回测。",
    type: "website",
    locale: "zh_CN",
  },
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
