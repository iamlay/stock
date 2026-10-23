import type { MetadataRoute } from "next";

const SITE_URL = "https://stock.iamlay.com";
const API_BASE =
  process.env.API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://127.0.0.1:8000";

type StockPage = {
  code: string;
  updated_at: string | null;
};

async function fetchStockCodes(): Promise<StockPage[]> {
  const items: StockPage[] = [];
  try {
    const first = await fetch(`${API_BASE}/api/v1/stocks?page=1&page_size=100`, {
      next: { revalidate: 3600 },
      signal: AbortSignal.timeout(10000),
    });
    if (!first.ok) return items;
    const firstBody = (await first.json()) as {
      items: StockPage[];
      total: number;
    };
    items.push(...firstBody.items);
    const pages = Math.min(60, Math.ceil(firstBody.total / 100));
    for (let page = 2; page <= pages; page += 1) {
      const response = await fetch(
        `${API_BASE}/api/v1/stocks?page=${page}&page_size=100`,
        {
          next: { revalidate: 3600 },
          signal: AbortSignal.timeout(10000),
        },
      );
      if (!response.ok) break;
      const body = (await response.json()) as { items: StockPage[] };
      items.push(...body.items);
    }
  } catch {
    return items;
  }
  return items;
}

async function fetchEtfCodes(): Promise<string[]> {
  try {
    const response = await fetch(`${API_BASE}/api/v1/etfs`, {
      next: { revalidate: 3600 },
      signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) return [];
    const body = (await response.json()) as { code: string }[];
    return body.map((item) => item.code);
  } catch {
    return [];
  }
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const stocks = await fetchStockCodes();
  const etfs = await fetchEtfCodes();
  const now = new Date();

  return [
    {
      url: SITE_URL,
      lastModified: now,
      changeFrequency: "daily",
      priority: 1,
    },
    {
      url: `${SITE_URL}/dashboard`,
      lastModified: now,
      changeFrequency: "daily",
      priority: 0.8,
    },
    {
      url: `${SITE_URL}/etf`,
      lastModified: now,
      changeFrequency: "daily",
      priority: 0.9,
    },
    {
      url: `${SITE_URL}/stocks`,
      lastModified: now,
      changeFrequency: "daily",
      priority: 0.9,
    },
    {
      url: `${SITE_URL}/pricing`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.4,
    },
    {
      url: `${SITE_URL}/legal/privacy`,
      lastModified: now,
      changeFrequency: "yearly",
      priority: 0.2,
    },
    ...stocks.map((stock) => ({
      url: `${SITE_URL}/stocks/${stock.code}`,
      lastModified: stock.updated_at ? new Date(stock.updated_at) : now,
      changeFrequency: "daily" as const,
      priority: 0.7,
    })),
    ...etfs.map((code) => ({
      url: `${SITE_URL}/etf/${code}`,
      lastModified: now,
      changeFrequency: "daily" as const,
      priority: 0.6,
    })),
  ];
}
