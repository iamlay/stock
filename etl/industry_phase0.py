from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

from etl.sources.industry import (
    fetch_eastmoney_industry,
    fetch_sina_industry_map,
)

SAMPLE_CODES = [
    "600519",
    "601398",
    "600036",
    "601088",
    "600028",
    "601857",
    "600900",
    "601318",
    "000651",
    "000333",
    "600690",
    "601166",
    "601288",
    "601988",
    "600030",
]


def run_probe(
    *,
    samples: int = 20,
    max_nodes: int | None = None,
    out_path: Path = Path("etl/out/stock_industry_phase0.json"),
) -> dict:
    nodes, sina_map = fetch_sina_industry_map(max_nodes=max_nodes)
    selected = SAMPLE_CODES[:samples]
    rows: list[dict] = []
    em_ok = 0
    for code in selected:
        try:
            company = fetch_eastmoney_industry(code)
            em_ok += 1
            rows.append(
                {
                    **asdict(company),
                    "sina_industry": sina_map.get(code),
                }
            )
        except Exception as exc:  # noqa: BLE001
            rows.append(
                {
                    "code": code,
                    "error": str(exc),
                    "sina_industry": sina_map.get(code),
                }
            )
        time.sleep(0.2)

    covered = sum(1 for row in rows if row.get("sina_industry"))
    report = {
        "sina_nodes": len(nodes),
        "sina_mapped_stocks": len(sina_map),
        "sample_count": len(rows),
        "sina_sample_coverage": covered,
        "eastmoney_sample_success": em_ok,
        "nodes": [asdict(node) for node in nodes],
        "stocks": rows,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def print_report(report: dict, out_path: Path) -> None:
    print(
        f"sina nodes={report['sina_nodes']} mapped={report['sina_mapped_stocks']} "
        f"sample_coverage={report['sina_sample_coverage']}/{report['sample_count']} "
        f"eastmoney_ok={report['eastmoney_sample_success']}/{report['sample_count']}"
    )
    print(f"{'code':8} {'sina':14} {'eastmoney':22} {'csrc':28} {'board'}")
    for row in report["stocks"]:
        print(
            f"{row.get('code', ''):8} "
            f"{row.get('sina_industry') or '-'!s:14} "
            f"{row.get('eastmoney_industry') or '-'!s:22} "
            f"{row.get('csrc_industry') or '-'!s:28} "
            f"{row.get('board') or '-'}"
        )
    print(f"report: {out_path}")
