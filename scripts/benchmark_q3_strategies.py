"""Paired synthetic ablation of q3 active-measurement strategies.

Every strategy sees the same generated sources and only receives protocol
replies.  Results are local synthetic evidence, not an official simulator
score.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from cumcm_b.policy import CoveragePolicy
from cumcm_b.protocol import RobotClient
from cumcm_b.synthetic import SyntheticArena, generate_sources


STRATEGIES = {
    "adaptive": 0.02,
    "adaptive_q25": 0.04,
    "adaptive_q25_fine": 0.04,
    "adaptive_q10": 0.02,
    "adaptive_q10_dynamic": 0.02,
    "adaptive_q10_dynamic_fine": 0.02,
}


def run(seed: int, strategy: str, travel_weight: float) -> dict:
    sources = generate_sources(seed, question=3)
    arena = SyntheticArena(sources, seed)
    result = CoveragePolicy(
        RobotClient(arena.process),
        question=3,
        strategy=strategy,
        travel_weight=travel_weight,
        dynamic_first_weight=0.50,
        dynamic_later_weight=0.02,
        candidate_angle_step=22.5,
    ).run()
    result.update(seed=seed, N=len(sources), scenario_origin="synthetic")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=50)
    parser.add_argument("--out", type=Path, default=Path(".local/q3-strategies"))
    args = parser.parse_args()
    if args.seeds < 2:
        parser.error("--seeds must be at least 2")
    args.out.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(args.seeds):
        seed = 20260911 + i
        for strategy, weight in STRATEGIES.items():
            row = run(seed, strategy, weight)
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(args.out / "runs.csv", index=False)
    pivot = frame.pivot(index="seed", columns="strategy")
    means = frame.groupby("strategy")["mean_clear_time_s"].mean().sort_values()
    baseline = pivot["mean_clear_time_s"]["adaptive"]
    summary = {
        "scenario_origin": "local_synthetic_not_official",
        "seeds": args.seeds,
        "travel_weights": STRATEGIES,
        "mean_s_per_source": {k: float(v) for k, v in means.items()},
        "paired_reduction_vs_adaptive_percent": {
            k: float(100 * (1 - pivot["mean_clear_time_s"][k].mean() / baseline.mean()))
            for k in STRATEGIES
        },
        "wins_vs_adaptive": {
            k: int((pivot["mean_clear_time_s"][k] < baseline).sum()) for k in STRATEGIES
        },
        "all_complete": bool(frame.completion_certificate.all() and frame.exit_ok.all()),
        "fallbacks_by_strategy": {
            k: int(frame.loc[frame.strategy == k, "fallback_actions"].sum()) for k in STRATEGIES
        },
        "interpretation": "paired synthetic ablation only; no official score claim",
    }
    (args.out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["all_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
