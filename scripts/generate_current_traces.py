"""Generate one auditable trace for each current q3/q4 entry point.

These traces are local synthetic records used only for figures and paper
walk-throughs.  They deliberately live beside the historical benchmark traces
so that a reader can tell which strategy produced the plotted actions.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cumcm_b.benchmark import run_case


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results/synthetic"))
    parser.add_argument("--seed", type=int, default=20260911)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    cases = [
        (3, "adaptive_q10_dynamic", "seven", "q3_current_trace.json"),
        (4, "q4_joint", "ring25", "q4_current_trace.json"),
    ]
    for question, strategy, coverage, filename in cases:
        result, trace = run_case(
            args.seed,
            question,
            strategy=strategy,
            trace=True,
            coverage=coverage,
        )
        if trace is None:
            raise RuntimeError(f"trace missing for q{question}")
        trace["metadata"] = {
            "scenario_origin": "local_synthetic_not_official",
            "seed": args.seed,
            "question": question,
            "strategy": strategy,
            "coverage": coverage,
            "result": result,
        }
        (args.out / filename).write_text(
            json.dumps(trace, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {args.out / filename}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
