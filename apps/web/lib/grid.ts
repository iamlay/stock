export const GRID_YIELDS = [4, 4.5, 5, 5.5, 6] as const;

export type GridTarget = {
  yield: number;
  price: number;
  distancePct: number;
};

export type StockGrid = {
  annualCash: number;
  currentYield: number;
  targets: GridTarget[];
};

export function buildGrid(
  price: number | null,
  ttmYield: number | null,
): StockGrid | null {
  if (!price || price <= 0 || ttmYield == null || ttmYield <= 0) return null;
  const annualCash = (price * ttmYield) / 100;
  if (annualCash <= 0) return null;

  return {
    annualCash,
    currentYield: ttmYield,
    targets: GRID_YIELDS.map((targetYield) => {
      const targetPrice = annualCash / (targetYield / 100);
      return {
        yield: targetYield,
        price: targetPrice,
        distancePct: (targetPrice / price - 1) * 100,
      };
    }),
  };
}
