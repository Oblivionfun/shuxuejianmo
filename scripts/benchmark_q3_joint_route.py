"""Evaluate a one-step look-ahead route for q3 (synthetic practice only).

The route score trades the distance to the next coverage station against the
nearest remaining station.  Localization and its MEC safety certificate are
delegated unchanged to :class:`CoveragePolicy`.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd

from cumcm_b.policy import CoveragePolicy, stations
from cumcm_b.protocol import BudgetExpired, ProtocolError, RobotClient
from cumcm_b.synthetic import SyntheticArena, generate_sources
from cumcm_b.geometry import enclosing_circle


class JointRoutePolicy(CoveragePolicy):
    """CoveragePolicy with a one-step pending-station look-ahead."""

    def _next_station(self, pending, points):
        cur = self.client.position
        if len(pending) <= 1:
            return pending[0]

        # Score is current leg plus a small look-ahead leg.  The coefficient
        # keeps coverage discovery primary while avoiding expensive dead ends.
        def score(i):
            d0 = float(((points[i] - cur) ** 2).sum() ** 0.5)
            d1 = min(float(((points[i] - points[j]) ** 2).sum() ** 0.5) for j in pending if j != i)
            return d0 + 0.35 * d1

        return min(pending, key=score)

    def run(self):
        started = time.monotonic()
        self.client.action("/enter")
        points = stations(self.question, self.coverage)
        pending = list(range(len(points)))
        complete, reason = False, "not_started"
        try:
            while pending:
                index = (
                    pending[0] if self.strategy == "fixed" else self._next_station(pending, points)
                )
                p = points[index]
                channels = [k for k, t in self.tracks.items() if not t.cleared]
                if self.client.channel in channels:
                    channels.remove(self.client.channel)
                    channels.insert(0, self.client.channel)
                for k in channels:
                    self.measure_at(k, p)
                    if self.client.metrics["cleared"] == 16:
                        complete, reason = True, "upper_bound_16"
                        break
                if complete:
                    break
                self.visited.append(index)
                pending.remove(index)
                known = [k for k, t in self.tracks.items() if t.seen and not t.cleared]
                while known:
                    k = min(
                        known,
                        key=lambda kk: float(
                            (
                                (
                                    enclosing_circle(self.tracks[kk].belief.polygon)[0]
                                    - self.client.position
                                )
                                ** 2
                            ).sum()
                            ** 0.5
                        ),
                    )
                    self.localize(k)
                    known.remove(k)
                if self.client.metrics["cleared"] == 16:
                    complete, reason = True, "upper_bound_16"
                    break
            if not pending and all(not t.seen or t.cleared for t in self.tracks.values()):
                complete, reason = True, "coverage_and_clearing"
        except BudgetExpired:
            reason = "budget_incomplete"
        except (ProtocolError, ArithmeticError) as exc:
            reason = f"error:{type(exc).__name__}:{exc}"
        exit_ok = False
        if not self.client.unresolved and self.client.remaining() > 0:
            try:
                self.client.action("/exit")
                exit_ok = True
            except ProtocolError as exc:
                reason += f";exit_error:{type(exc).__name__}"
        count = self.client.metrics["cleared"]
        return {
            "question": self.question,
            "strategy": self.strategy,
            "coverage": self.coverage,
            "completion_certificate": complete,
            "completion_reason": reason,
            "exit_ok": exit_ok,
            "virtual_time_s": self.client.virtual_time,
            "mean_clear_time_s": self.client.virtual_time / count if count else None,
            "real_runtime_s": time.monotonic() - started,
            "stations_visited": len(self.visited),
            "fallback_actions": self.fallback_actions,
            **self.client.metrics,
        }


def run(seed, strategy):
    arena = SyntheticArena(generate_sources(seed, question=3), seed)
    client = RobotClient(arena.process)
    cls = JointRoutePolicy if strategy == "joint_route" else CoveragePolicy
    result = cls(client, question=3, strategy="adaptive_q25", travel_weight=0.04).run()
    result.update(seed=seed, strategy=strategy, N=len(arena.sources), scenario_origin="synthetic")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--out", type=Path, default=Path(".local/q3-joint-route"))
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    rows = [run(20260911 + i, s) for i in range(a.seeds) for s in ("adaptive_q25", "joint_route")]
    frame = pd.DataFrame(rows)
    frame.to_csv(a.out / "runs.csv", index=False)
    p = frame.pivot(index="seed", columns="strategy", values="mean_clear_time_s")
    summary = {
        "seeds": a.seeds,
        "baseline": "adaptive_q25",
        "candidate": "joint_route",
        "baseline_s_per_source": float(p.adaptive_q25.mean()),
        "candidate_s_per_source": float(p.joint_route.mean()),
        "reduction_percent": float(100 * (1 - p.joint_route.mean() / p.adaptive_q25.mean())),
        "wins": int((p.joint_route < p.adaptive_q25).sum()),
        "all_complete": bool(frame.completion_certificate.all() and frame.exit_ok.all()),
        "interpretation": "synthetic fixed seeds only",
    }
    (a.out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
