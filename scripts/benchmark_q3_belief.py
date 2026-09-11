"""Compare a feedback-only Bayesian occupancy-grid query policy on q3.

The policy samples the current outer feasible polygon, treats those samples as
an occupancy belief, and ranks the existing guaranteed-reception query points
by expected post-measurement angular uncertainty plus travel cost.  It never
accesses SyntheticArena.sources; the arena is only the black-box evaluator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from cumcm_b.geometry import candidate_points, enclosing_circle, optical_cover_points
from cumcm_b.policy import CoveragePolicy
from cumcm_b.protocol import ProtocolError, RobotClient
from cumcm_b.synthetic import SyntheticArena, generate_sources


def _belief_samples(belief, n=256, boundary_count=0):
    """Deterministically sample a convex outer polygon from observations only."""
    poly = np.asarray(belief.polygon, dtype=float)
    if len(poly) == 1:
        return poly.copy()
    if len(poly) == 2:
        t = (np.arange(n, dtype=float) + 0.5) / n
        return poly[0] + t[:, None] * (poly[1] - poly[0])

    # A seed derived only from the public belief history makes repeated calls
    # stable while avoiding a fixed lattice aligned with candidate bearings.
    digest = hashlib.blake2b(digest_size=8)
    for position, bearing in belief.observations:
        digest.update(np.asarray(position, dtype=np.float64).tobytes())
        digest.update(float(bearing).hex().encode())
    seed = int.from_bytes(digest.digest(), "big") % (2**32)
    rng = np.random.default_rng(seed)
    p0 = poly[0]
    triangles = np.stack((np.broadcast_to(p0, (len(poly) - 2, 2)), poly[1:-1], poly[2:]), axis=1)
    areas = np.abs(
        (triangles[:, 1, 0] - triangles[:, 0, 0]) * (triangles[:, 2, 1] - triangles[:, 0, 1])
        - (triangles[:, 1, 1] - triangles[:, 0, 1]) * (triangles[:, 2, 0] - triangles[:, 0, 0])
    )
    if not np.any(areas > 1e-12):
        return np.vstack((poly, np.mean(poly, axis=0)))
    probabilities = areas / areas.sum()
    triangle_ids = rng.choice(len(triangles), size=n, p=probabilities)
    uv = rng.random((n, 2))
    over = uv.sum(axis=1) > 1.0
    uv[over] = 1.0 - uv[over]
    tri = triangles[triangle_ids]
    interior = (
        tri[:, 0]
        + uv[:, 0, None] * (tri[:, 1] - tri[:, 0])
        + uv[:, 1, None] * (tri[:, 2] - tri[:, 0])
    )
    if boundary_count <= 0:
        return interior
    boundary = np.vstack((poly, (poly + np.roll(poly, -1, axis=0)) / 2.0))
    boundary_ids = np.arange(boundary_count) % len(boundary)
    return np.vstack((interior, boundary[boundary_ids]))


def _expected_rms(q, samples, error_deg):
    """Expected residual position spread after a rounded bounded-angle reply."""
    delta = samples - np.asarray(q, dtype=float)
    angles = np.mod(np.degrees(np.arctan2(delta[:, 1], delta[:, 0])), 360.0)
    # A 2*epsilon bin is a conservative surrogate for a bounded +/-epsilon
    # reply.  no_signal is not assigned a zero-probability bin: all candidate
    # points are certified within 1000 m of the whole polygon for q3.
    width = 2.0 * float(error_deg)
    bins = np.floor(angles / width).astype(np.int64)
    residual = 0.0
    for key in np.unique(bins):
        cluster = samples[bins == key]
        cluster_delta = delta[bins == key]
        center = cluster.mean(axis=0)
        radial = float(np.sqrt(np.mean(np.sum((cluster - center) ** 2, axis=1))))
        angular_floor = float(np.mean(np.linalg.norm(cluster_delta, axis=1))) * math.sin(
            math.radians(error_deg)
        )
        probability = len(cluster) / len(samples)
        residual += probability * math.hypot(radial, angular_floor)
    return float(residual)


class BeliefGridPolicy(CoveragePolicy):
    """CoveragePolicy with an online occupancy-grid query ranking."""

    def __init__(self, *args, sample_count=256, boundary_count=0, bayes_weight=1.0, **kwargs):
        super().__init__(*args, **kwargs)
        self.sample_count = int(sample_count)
        self.boundary_count = int(boundary_count)
        self.bayes_weight = float(bayes_weight)
        self.query_diagnostics = []

    def localize(self, k):
        track = self.tracks[k]
        attempted = []
        for _ in range(self.max_active):
            if track.cleared:
                return
            center, radius = enclosing_circle(track.belief.polygon)
            if radius <= 19.75:
                if not self.clear_at(k, center, "enclosing_circle"):
                    raise ProtocolError("certified sub-20m clear failed")
                return
            candidates = candidate_points(
                track.belief, self.client.position, self.travel_weight, objective="q25"
            )
            candidates = [
                row
                for row in candidates
                if all(np.linalg.norm(row["position"] - old) > 1.0 for old in attempted)
            ]
            if not candidates:
                break
            samples = _belief_samples(track.belief, self.sample_count, self.boundary_count)
            ranked = []
            for row in candidates:
                q = row["position"]
                residual = _expected_rms(q, samples, track.belief.error_deg)
                travel = float(np.linalg.norm(q - self.client.position))
                score = self.bayes_weight * residual + self.travel_weight * travel
                ranked.append((score, residual, travel, row))
            _, residual, travel, selected = min(ranked, key=lambda item: item[0])
            q = selected["position"]
            self.query_diagnostics.append(
                {
                    "channel": k,
                    "samples": len(samples),
                    "expected_residual_m": residual,
                    "travel_m": travel,
                    "score": float(min(ranked, key=lambda item: item[0])[0]),
                }
            )
            attempted.append(q.copy())
            self.measure_at(k, q)
        if track.cleared:
            return
        center, radius = enclosing_circle(track.belief.polygon)
        if radius <= 19.75:
            if not self.clear_at(k, center, "enclosing_circle"):
                raise ProtocolError("certified sub-20m clear failed")
            return
        points = list(optical_cover_points(track.belief))
        self.events.append(
            {"event": "fallback", "channel": k, "cells": len(points), "radius_m": radius}
        )
        while points:
            i = int(np.argmin([np.linalg.norm(p - self.client.position) for p in points]))
            p = points.pop(i)
            self.fallback_actions += 1
            if self.clear_at(k, p, "optical_grid"):
                return
        raise ProtocolError("exhausted certified optical cover without success")


def run(seed: int, strategy: str, travel_weight: float, sample_count: int, boundary_count: int = 0):
    sources = generate_sources(seed, question=3)
    arena = SyntheticArena(sources, seed)
    client = RobotClient(arena.process)
    if strategy == "adaptive_q25":
        policy = CoveragePolicy(client, question=3, strategy=strategy, travel_weight=travel_weight)
    elif strategy == "belief_grid":
        policy = BeliefGridPolicy(
            client,
            question=3,
            strategy="adaptive_q25",
            travel_weight=travel_weight,
            sample_count=sample_count,
            boundary_count=boundary_count,
        )
    else:
        raise ValueError(strategy)
    result = policy.run()
    result.update(seed=seed, N=len(sources), scenario_origin="synthetic")
    if strategy == "belief_grid":
        result.update(
            strategy=strategy,
            query_count=len(policy.query_diagnostics),
            mean_expected_residual_m=(
                float(np.mean([x["expected_residual_m"] for x in policy.query_diagnostics]))
                if policy.query_diagnostics
                else None
            ),
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--out", type=Path, default=Path(".local/q3-belief-grid"))
    parser.add_argument("--sample-count", type=int, default=256)
    parser.add_argument(
        "--boundary-count",
        type=int,
        default=0,
        help="extra boundary-critical samples for belief_grid",
    )
    parser.add_argument(
        "--travel-weight", type=float, default=0.04, help="baseline adaptive_q25 travel weight"
    )
    parser.add_argument(
        "--bayes-travel-weight",
        type=float,
        default=None,
        help="belief-grid travel weight; defaults to --travel-weight",
    )
    args = parser.parse_args()
    if args.seeds < 2 or args.sample_count < 32 or args.boundary_count < 0:
        parser.error("--seeds >=2, --sample-count >=32, and --boundary-count >=0 are required")
    if args.bayes_travel_weight is None:
        args.bayes_travel_weight = args.travel_weight
    args.out.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(args.seeds):
        seed = 20260911 + i
        for strategy in ("adaptive_q25", "belief_grid"):
            weight = args.travel_weight if strategy == "adaptive_q25" else args.bayes_travel_weight
            row = run(seed, strategy, weight, args.sample_count, args.boundary_count)
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(args.out / "runs.csv", index=False)
    paired = frame.pivot(index="seed", columns="strategy", values="mean_clear_time_s")
    summary = {
        "scenario_origin": "local_synthetic_not_official",
        "seeds": args.seeds,
        "baseline": "adaptive_q25",
        "candidate": "belief_grid",
        "sample_count": args.sample_count,
        "boundary_count": args.boundary_count,
        "travel_weight": {
            "adaptive_q25": args.travel_weight,
            "belief_grid": args.bayes_travel_weight,
        },
        "baseline_s_per_source": float(paired.adaptive_q25.mean()),
        "candidate_s_per_source": float(paired.belief_grid.mean()),
        "mean_reduction_percent": float(
            100 * (1 - paired.belief_grid.mean() / paired.adaptive_q25.mean())
        ),
        "wins": int((paired.belief_grid < paired.adaptive_q25).sum()),
        "all_complete": bool(frame.completion_certificate.all() and frame.exit_ok.all()),
        "interpretation": "belief-grid query ranking improves this fixed synthetic seed set only; no official score claim",
    }
    (args.out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["all_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
