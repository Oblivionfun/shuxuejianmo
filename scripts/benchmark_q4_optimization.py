"""Paired synthetic benchmark for the optimized q4 coverage-and-route policy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from cumcm_b.policy import CoveragePolicy
from cumcm_b.protocol import RobotClient
from cumcm_b.synthetic import SyntheticArena, generate_sources


VARIANTS = {
    "legacy_adaptive": ("triangular_legacy", "adaptive", 0.02),
    "optimized_adaptive": ("triangular", "adaptive", 0.02),
    "optimized_q4_joint": ("triangular", "q4_joint", 0.02),
    "ring25_q4_joint": ("ring25", "q4_joint", 0.02),
}


def run(seed: int, name: str) -> dict:
    coverage, strategy, weight = VARIANTS[name]
    sources = generate_sources(seed, question=4)
    arena = SyntheticArena(sources, seed)
    result = CoveragePolicy(
        RobotClient(arena.process),
        question=4,
        strategy=strategy,
        travel_weight=weight,
        coverage=coverage,
        q4_objective="q10" if strategy == "q4_joint" else "worst",
        q4_final_order="tsp" if strategy == "q4_joint" else "nearest",
        defer_q4_localization=True,
    ).run()
    result.update(
        seed=seed,
        N=len(sources),
        variant=name,
        scenario_origin="synthetic",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=50)
    parser.add_argument("--start", type=int, default=20261011)
    parser.add_argument("--out", type=Path, default=Path("results/synthetic/q4_optimization"))
    args = parser.parse_args()
    if args.seeds < 2:
        parser.error("--seeds must be at least 2")
    args.out.mkdir(parents=True, exist_ok=True)
    rows = [
        run(args.start + i, name)
        for i in range(args.seeds)
        for name in VARIANTS
    ]
    frame = pd.DataFrame(rows)
    frame.to_csv(args.out / "runs.csv", index=False)
    pivot = frame.pivot(index="seed", columns="variant", values="mean_clear_time_s")
    summary = {
        "scenario_origin": "local_synthetic_not_official",
        "seeds": args.seeds,
        "variants": VARIANTS,
        "mean_s_per_source": {
            name: float(pivot[name].mean()) for name in VARIANTS
        },
        "mean_distance_m": {
            name: float(frame.loc[frame.variant == name, "distance_m"].mean())
            for name in VARIANTS
        },
        "all_complete": bool(frame.completion_certificate.all() and frame.exit_ok.all()),
        "joint_wins_vs_optimized_adaptive": int(
            (pivot["optimized_q4_joint"] < pivot["optimized_adaptive"]).sum()
        ),
        "joint_reduction_vs_optimized_adaptive_percent": float(
            100
            * (1 - pivot["optimized_q4_joint"].mean() / pivot["optimized_adaptive"].mean())
        ),
        "joint_reduction_vs_legacy_percent": float(
            100
            * (1 - pivot["optimized_q4_joint"].mean() / pivot["legacy_adaptive"].mean())
        ),
        "ring25_wins_vs_triangular_joint": int(
            (pivot["ring25_q4_joint"] < pivot["optimized_q4_joint"]).sum()
        ),
        "ring25_reduction_vs_triangular_joint_percent": float(
            100
            * (1 - pivot["ring25_q4_joint"].mean() / pivot["optimized_q4_joint"].mean())
        ),
        "interpretation": "paired synthetic ablation only; no official score claim",
    }
    (args.out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["all_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
