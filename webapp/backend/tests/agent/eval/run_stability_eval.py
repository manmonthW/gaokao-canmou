#!/usr/bin/env python3
"""Run one representative recommendation query five times and score overlap."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
BACKEND_DIR = next(
    root for root in (Path("/app"), *EVAL_DIR.parents) if (root / "app").is_dir()
)
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from run_real_eval import _run_case  # noqa: E402
from app.agent.prompts import PROMPTS_VERSION  # noqa: E402


def _overlap(sets: list[set[str]]) -> float:
    union = set().union(*sets)
    return len(set.intersection(*sets)) / len(union) if union else 1.0


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=EVAL_DIR / "cases.yaml")
    parser.add_argument("--case-id", default="find-01")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--output", type=Path, default=EVAL_DIR / "stability-results.json")
    parser.add_argument("--report", type=Path, default=EVAL_DIR / "stability-report.md")
    args = parser.parse_args()

    suite = json.loads(args.cases.read_text(encoding="utf-8"))
    case = next((item for item in suite["cases"] if item["id"] == args.case_id), None)
    if case is None:
        parser.error(f"unknown case id: {args.case_id}")

    results = []
    for run in range(1, args.runs + 1):
        row = await _run_case({**case, "id": f"{case['id']}-run-{run}"}, args.timeout)
        results.append(row)
        print(f"[{run}/{args.runs}] {row['status']} ({row['duration_ms']} ms)")

    completed = [row for row in results if row["status"] == "completed"]
    sets = [set(row["recommended_units"]) for row in completed]
    overlap = _overlap(sets) if len(sets) == args.runs else 0.0
    summary = {
        "suite_version": suite["version"],
        "prompt_version": PROMPTS_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_id": args.case_id,
        "runs": args.runs,
        "completed": len(completed),
        "intersection_over_union_pct": round(overlap * 100, 1),
        "gate_passed": len(completed) == args.runs and overlap >= 0.70,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Agent Phase 1 Recommendation Stability",
        "",
        f"- Suite: `{suite['version']}`",
        f"- Prompt: `{PROMPTS_VERSION}`",
        f"- Generated: `{summary['generated_at']}`",
        f"- Representative case: `{args.case_id}`",
        f"- Completed: `{len(completed)}/{args.runs}`",
        f"- Five-set intersection/union overlap: **{summary['intersection_over_union_pct']}%**",
        f"- Gate >= 70%: **{'PASS' if summary['gate_passed'] else 'FAIL'}**",
        "",
        "## Runs",
        "",
        "| Run | Status | Duration | Recommendations |",
        "|---:|---|---:|---|",
    ]
    for index, row in enumerate(results, start=1):
        units = ", ".join(row.get("recommended_units") or []) or "-"
        lines.append(f"| {index} | {row['status']} | {row['duration_ms'] / 1000:.2f}s | {units} |")
    lines.extend([
        "",
        "Overlap is the intersection of all five recommendation sets divided by their union. This is stricter than averaging pairwise overlap.",
    ])
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}, ensure_ascii=False, indent=2))
    return 0 if summary["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
