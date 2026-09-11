"""All reported scores here are LOCAL SYNTHETIC, never official simulator results."""

from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
from cumcm_b.geometry import (
    Belief,
    unit,
    candidate_points,
    enclosing_circle,
    bearing_intersection,
    diameter_bruteforce,
)
from cumcm_b.protocol import RobotClient
from cumcm_b.synthetic import SyntheticArena, generate_sources, source_rows
from cumcm_b.policy import CoveragePolicy, stations


def run_case(
    seed,
    question,
    strategy="adaptive",
    stress=None,
    error_mode="fixed_location",
    trace=False,
    coverage="triangular",
):
    sources = generate_sources(seed, question, stress=stress)
    arena = SyntheticArena(sources, seed, error_mode)
    client = RobotClient(arena.process)
    policy = CoveragePolicy(client, question, strategy, coverage=coverage)
    result = policy.run()
    result.update(
        scenario_origin="synthetic",
        seed=seed,
        N=len(sources),
        completion_ratio=len(arena.cleared) / len(sources),
        stress=stress or "none",
        error_mode=error_mode,
    )
    if result["completion_certificate"] and len(arena.cleared) != len(sources):
        raise AssertionError("false completion certificate")
    details = None
    if trace:
        details = {
            "sources": source_rows(sources),
            "stations": stations(question, coverage).tolist(),
            "visited": policy.visited,
            "records": client.records,
            "events": policy.events,
            "beliefs": {
                str(k): t.belief.history for k, t in policy.tracks.items() if t.belief.history
            },
        }
    return result, details


def geometry_examples(out):
    side = 39.0
    tri = np.array([[0, 0], [side, 0], [side / 2, side * math.sqrt(3) / 2]])
    obs = []
    for p, q in zip(tri, np.roll(tri, -1, axis=0)):
        e = (q - p) / np.linalg.norm(q - p)
        obs.append((p - 1200 * e, (math.degrees(math.atan2(e[1], e[0])) + 1) % 360))
    result = bearing_intersection(obs)
    c, r = enclosing_circle(result["vertices"])
    q1 = {
        "scenario_origin": "constructed",
        "observations": [{"position": p.tolist(), "bearing_deg": t} for p, t in obs],
        "polygon": result["vertices"].tolist(),
        "diameter_m": result["diameter_m"],
        "bruteforce_m": diameter_bruteforce(result["vertices"]),
        "circle_center": c.tolist(),
        "circle_radius_m": r,
        "diameter_pair": result["diameter_pair"].tolist(),
    }
    (out / "q1.json").write_text(json.dumps(q1, indent=2), encoding="utf-8")
    b = Belief()
    b.observe([0, 0], 0)
    candidate_rows = []
    experiment_rows = []
    for weight in (0.0, 0.02, 0.05):
        ranked = candidate_points(b, np.zeros(2), weight)
        for rank, row in enumerate(ranked):
            candidate_rows.append(
                {
                    "travel_weight": weight,
                    "rank": rank,
                    "x_m": row["position"][0],
                    "y_m": row["position"][1],
                    **{k: v for k, v in row.items() if k != "position"},
                }
            )
        selected = ranked[0]["position"]
        for distance in (100.0, 300.0, 600.0, 900.0, 1200.0, 1490.0):
            for initial_error in (-1.0, 0.0, 1.0):
                truth = distance * unit(-initial_error)
                actual = math.degrees(math.atan2(*(truth - selected)[::-1])) % 360
                for second_error in (-1.0, 0.0, 1.0):
                    posterior = Belief()
                    posterior.observe([0, 0], 0)
                    posterior.observe(selected, (actual + second_error) % 360)
                    cc, rr = enclosing_circle(posterior.polygon)
                    experiment_rows.append(
                        {
                            "scenario_origin": "synthetic",
                            "travel_weight": weight,
                            "source_range_m": distance,
                            "initial_error_deg": initial_error,
                            "second_error_deg": second_error,
                            "posterior_radius_m": rr,
                            "actual_error_m": np.linalg.norm(cc - truth),
                            "travel_m": np.linalg.norm(selected),
                            "received": np.linalg.norm(selected - truth) <= 1000,
                            "source_in_circle": np.linalg.norm(cc - truth) <= rr + 1e-7,
                        }
                    )
    pd.DataFrame(candidate_rows).to_csv(out / "q2_candidates.csv", index=False)
    pd.DataFrame(experiment_rows).to_csv(out / "q2_validation.csv", index=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--cases", type=int, default=20)
    parser.add_argument("--out", type=Path, default=Path(".local/benchmarks"))
    args = parser.parse_args()
    if args.cases < 1:
        parser.error("--cases must be positive")
    args.out.mkdir(parents=True, exist_ok=True)
    geometry_examples(args.out)
    results = []
    for question in (3, 4):
        for i in range(1 if args.smoke else args.cases):
            seed = 20260911 + i
            for strategy in ["adaptive"] if args.smoke else ["fixed", "adaptive"]:
                row, trace = run_case(
                    seed, question, strategy, trace=(i == 0 and strategy == "adaptive")
                )
                results.append(row)
                print(json.dumps(row), flush=True)
                if trace:
                    (args.out / f"q{question}_trace.json").write_text(
                        json.dumps(trace, indent=2), encoding="utf-8"
                    )
        if not args.smoke:
            for stress, mode in [
                ("outward_boundary", "positive"),
                ("outward_boundary", "negative"),
                (None, "spatial"),
            ]:
                row, trace = run_case(909, question, "adaptive", stress, mode, trace=False)
                results.append(row)
                print(json.dumps(row), flush=True)
    df = pd.DataFrame(results)
    df.to_csv(args.out / "runs.csv", index=False)
    coverage_comparison = []
    if not args.smoke:
        coverage_comparison = df[
            (df.question == 4)
            & (df.strategy == "adaptive")
            & (df.stress == "none")
            & (df.error_mode == "fixed_location")
        ].to_dict("records")
        for i in range(args.cases):
            row, _ = run_case(20260911 + i, 4, "adaptive", coverage="square")
            coverage_comparison.append(row)
            print(json.dumps(row), flush=True)
        pd.DataFrame(coverage_comparison).to_csv(args.out / "coverage_comparison.csv", index=False)
    success = bool(
        df.completion_certificate.all() and (df.completion_ratio == 1).all() and df.exit_ok.all()
    )
    if coverage_comparison:
        success = success and all(
            r["completion_certificate"] and r["completion_ratio"] == 1 and r["exit_ok"]
            for r in coverage_comparison
        )
    extra = args.cases if not args.smoke else 0
    (args.out / "validation.json").write_text(
        json.dumps(
            {
                "all_complete": success,
                "cases": len(df) + extra,
                "main_runs": len(df),
                "extra_square_runs": extra,
                "official_results": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    comparisons = []
    if not args.smoke:
        base = df[(df.stress == "none") & (df.error_mode == "fixed_location")]
        for question in (3, 4):
            paired = base[base.question == question].pivot(
                index="seed", columns="strategy", values="mean_clear_time_s"
            )
            comparisons.append(
                {
                    "question": question,
                    "paired_seeds": len(paired),
                    "fixed_s_per_source": paired.fixed.mean(),
                    "adaptive_s_per_source": paired.adaptive.mean(),
                    "mean_reduction_percent": 100
                    * (1 - paired.adaptive.mean() / paired.fixed.mean()),
                    "wins": int((paired.adaptive < paired.fixed).sum()),
                }
            )
    grid_comparison = None
    if coverage_comparison:
        paired = pd.DataFrame(coverage_comparison).pivot(
            index="seed", columns="coverage", values="mean_clear_time_s"
        )
        grid_comparison = {
            "question": 4,
            "paired_seeds": len(paired),
            "square_s_per_source": paired.square.mean(),
            "triangular_s_per_source": paired.triangular.mean(),
            "mean_reduction_percent": 100 * (1 - paired.triangular.mean() / paired.square.mean()),
            "wins": int((paired.triangular < paired.square).sum()),
            "strategy": "adaptive",
        }
    summary = {
        "scenario_origin": "local_synthetic_not_official",
        "runs": len(df) + extra,
        "main_runs": len(df),
        "all_complete": success,
        "paired_base_results": comparisons,
        "coverage_comparison": grid_comparison,
    }
    (args.out / "comparison_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
