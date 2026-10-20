"use client";

import { useRouter } from "next/navigation";

export function StrategyCodePicker({
  options,
  value,
}: {
  options: { code: string; name: string }[];
  value: string;
}) {
  const router = useRouter();

  return (
    <label className="flex items-center gap-2 text-xs text-muted">
      <span className="whitespace-nowrap">回测标的</span>
      <select
        value={value}
        onChange={(event) => {
          router.push(`/strategies?code=${event.target.value}`);
        }}
        className="max-w-56 rounded-sm border border-line bg-surface px-2 py-1.5 text-xs text-ink"
      >
        {options.map((option) => (
          <option key={option.code} value={option.code}>
            {option.code} {option.name}
          </option>
        ))}
      </select>
    </label>
  );
}
