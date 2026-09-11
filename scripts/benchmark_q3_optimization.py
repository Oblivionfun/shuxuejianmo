"""Compare q3 active-measurement objectives on fixed synthetic seeds."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from cumcm_b.policy import CoveragePolicy
from cumcm_b.protocol import RobotClient
from cumcm_b.synthetic import SyntheticArena, generate_sources


def run(seed: int, strategy: str, travel_weight: float):
    sources = generate_sources(seed, question=3)
    arena = SyntheticArena(sources, seed)
    client = RobotClient(arena.process)
    result = CoveragePolicy(
        client, question=3, strategy=strategy, travel_weight=travel_weight
    ).run()
    result.update(seed=seed, N=len(sources), scenario_origin="synthetic")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=50)
    parser.add_argument("--out", type=Path, default=Path(".local/q3-optimization"))
    args = parser.parse_args()
    if args.seeds < 2:
        parser.error("--seeds must be at least 2")
    args.out.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(args.seeds):
        seed = 20260911 + i
        for strategy, weight in (("adaptive", 0.02), ("adaptive_q25", 0.04)):
            row = run(seed, strategy, weight)
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(args.out / "runs.csv", index=False)
    paired = frame.pivot(index="seed", columns="strategy", values="mean_clear_time_s")
    summary = {
        "scenario_origin": "local_synthetic_not_official",
        "seeds": args.seeds,
        "baseline": "adaptive",
        "candidate": "adaptive_q25",
        "travel_weights": {"adaptive": 0.02, "adaptive_q25": 0.04},
        "baseline_s_per_source": float(paired.adaptive.mean()),
        "candidate_s_per_source": float(paired.adaptive_q25.mean()),
        "mean_reduction_percent": float(
            100 * (1 - paired.adaptive_q25.mean() / paired.adaptive.mean())
        ),
        "wins": int((paired.adaptive_q25 < paired.adaptive).sum()),
        "all_complete": bool(frame.completion_certificate.all() and frame.exit_ok.all()),
        "interpretation": "candidate improves this fixed synthetic seed set only; no official score claim",
    }
    (args.out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["all_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
