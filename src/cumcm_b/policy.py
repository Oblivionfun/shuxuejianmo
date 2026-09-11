"""Coverage-certified discovery and bounded-error localization using feedback only."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import math
import time
import numpy as np
from shapely.geometry import Point, Polygon
from .geometry import Belief, candidate_points, enclosing_circle, optical_cover_points, unit
from .protocol import BudgetExpired, ProtocolError


@lru_cache(maxsize=1)
def _triangular_geometry():
    """Closed-cell construction; distance-to-origin tests the exact circular boundary."""
    side = 950.0

    def xy(i, j):
        return np.array(
            [side * (i + 1 / 3 + (j + 1 / 3) / 2), side * math.sqrt(3) / 2 * (j + 1 / 3)]
        )

    keys = set()
    cells = []
    for i in range(-5, 5):
        for j in range(-5, 5):
            for ids in (((i, j), (i + 1, j), (i, j + 1)), ((i + 1, j), (i + 1, j + 1), (i, j + 1))):
                tri = np.array([xy(*ij) for ij in ids])
                if Polygon(tri).distance(Point(0, 0)) <= 1800 + 1e-8:
                    keys.update(ids)
                    cells.append(tri)
    ordered = sorted(keys, key=lambda ij: (ij[1], ij[0] if ij[1] % 2 == 0 else -ij[0]))
    return np.vstack((np.zeros(2), [xy(*ij) for ij in ordered])), np.array(cells)


def triangular_cover():
    points, cells = _triangular_geometry()
    return points.copy(), cells.copy()


def stations(question, coverage="triangular"):
    if question == 3:
        return np.vstack((np.zeros(2), [900 * math.sqrt(3) * unit(t) for t in range(0, 360, 60)]))
    if question == 4:
        if coverage == "triangular":
            return triangular_cover()[0]
        if coverage != "square":
            raise ValueError("unknown q4 coverage")
        grid = []
        for row, y in enumerate(range(-1800, 1801, 600)):
            xs = list(range(-1800, 1801, 600))
            if row % 2:
                xs.reverse()
            grid.extend(np.array([x, y], float) for x in xs if x or y)
        return np.vstack((np.zeros(2), grid))
    raise ValueError("question must be 3 or 4")


@dataclass
class Track:
    belief: Belief = field(default_factory=Belief)
    cleared: bool = False
    seen: bool = False


class CoveragePolicy:
    def __init__(
        self,
        client,
        question=3,
        strategy="adaptive",
        travel_weight=0.02,
        max_active=6,
        coverage="triangular",
        dynamic_first_weight=0.50,
        dynamic_later_weight=0.02,
        candidate_angle_step=22.5,
    ):
        if strategy not in (
            "adaptive",
            "fixed",
            "adaptive_p90",
            "adaptive_q10",
            "adaptive_q10_dynamic",
            "adaptive_q10_dynamic_fine",
            "adaptive_q25",
            "adaptive_q25_fine",
            "adaptive_median",
        ):
            raise ValueError("unknown strategy")
        self.client = client
        self.question = question
        self.strategy = strategy
        self.coverage = "seven" if question == 3 else coverage
        self.travel_weight = travel_weight
        self.max_active = max_active
        self.dynamic_first_weight = float(dynamic_first_weight)
        self.dynamic_later_weight = float(dynamic_later_weight)
        self.candidate_angle_step = float(candidate_angle_step)
        self.tracks = {k: Track() for k in range(1, 21)}
        self.visited = []
        self.fallback_actions = 0
        self.events = []

    def clear_at(self, k, p, reason):
        reply = self.client.action("/clear", p, k)
        if reply["clear_result"] == "success":
            self.tracks[k].cleared = True
            self.events.append(
                {
                    "event": "cleared",
                    "channel": k,
                    "reason": reason,
                    "virtual_time_s": self.client.virtual_time,
                    "position": self.client.position.tolist(),
                }
            )
            return True
        return False

    def measure_at(self, k, p):
        reply = self.client.action("/measure", p, k)
        track = self.tracks[k]
        kind = reply["measure_result"]
        if kind == "near":
            track.seen = True
            if not self.clear_at(k, p, "near"):
                raise ProtocolError("near followed by failed same-position clear")
        elif kind == "direction":
            track.seen = True
            track.belief.observe(p, reply["svd_deg"])
        return kind

    def localize(self, k):
        track = self.tracks[k]
        attempted = []
        for _ in range(self.max_active):
            if track.cleared:
                return
            c, r = enclosing_circle(track.belief.polygon)
            if r <= 19.75:
                if not self.clear_at(k, c, "enclosing_circle"):
                    raise ProtocolError("certified sub-20m clear failed")
                return
            objective = {
                "adaptive": "worst",
                "adaptive_p90": "p90",
                "adaptive_q25": "q25",
                "adaptive_q25_fine": "q25",
                "adaptive_q10": "q10",
                "adaptive_q10_dynamic": "q10",
                "adaptive_q10_dynamic_fine": "q10",
                "adaptive_median": "median",
                "fixed": "worst",
            }[self.strategy]
            # The first active query is a coarse acquisition step: avoid a long
            # detour before the bearing history has narrowed the feasible set.
            # Once one or more active bearings exist, information gain dominates
            # because the next query is evaluated inside an already localised
            # cone.  This keeps the policy feedback-only and certificate-safe.
            travel_weight = self.travel_weight
            if self.strategy == "adaptive_q10_dynamic":
                travel_weight = (
                    self.dynamic_first_weight
                    if len(track.belief.observations) <= 1
                    else self.dynamic_later_weight
                )
            candidates = candidate_points(
                track.belief,
                self.client.position,
                travel_weight,
                objective=objective,
                angle_step=(
                    11.25
                    if self.strategy in {"adaptive_q25_fine", "adaptive_q10_dynamic_fine"}
                    else self.candidate_angle_step
                ),
            )
            choices = [
                row
                for row in candidates
                if all(np.linalg.norm(row["position"] - old) > 1.0 for old in attempted)
            ]
            if not choices:
                break
            q = choices[0]["position"]
            attempted.append(q.copy())
            self.measure_at(k, q)
        if track.cleared:
            return
        # A last measurement can already certify a small circle.
        c, r = enclosing_circle(track.belief.polygon)
        if r <= 19.75:
            if not self.clear_at(k, c, "enclosing_circle"):
                raise ProtocolError("certified sub-20m clear failed")
            return
        points = list(optical_cover_points(track.belief))
        self.events.append({"event": "fallback", "channel": k, "cells": len(points), "radius_m": r})
        while points:
            i = int(np.argmin([np.linalg.norm(p - self.client.position) for p in points]))
            p = points.pop(i)
            self.fallback_actions += 1
            if self.clear_at(k, p, "optical_grid"):
                return
        raise ProtocolError("exhausted certified optical cover without success")

    def run(self):
        started = time.monotonic()
        self.client.action("/enter")
        points = stations(self.question, self.coverage)
        pending = list(range(len(points)))
        complete = False
        reason = "not_started"
        try:
            while pending:
                index = (
                    pending[0]
                    if self.strategy == "fixed"
                    else min(
                        pending, key=lambda i: np.linalg.norm(points[i] - self.client.position)
                    )
                )
                p = points[index]
                channels = [k for k, t in self.tracks.items() if not t.cleared]
                if self.client.channel in channels:
                    channels.remove(self.client.channel)
                    channels.insert(0, self.client.channel)
                for k in channels:
                    self.measure_at(k, p)
                    if self.client.metrics["cleared"] == 16:
                        complete = True
                        reason = "upper_bound_16"
                        break
                if complete:
                    break
                self.visited.append(index)
                pending.remove(index)
                known = [k for k, t in self.tracks.items() if t.seen and not t.cleared]
                while known:
                    k = min(
                        known,
                        key=lambda kk: np.linalg.norm(
                            enclosing_circle(self.tracks[kk].belief.polygon)[0]
                            - self.client.position
                        ),
                    )
                    self.localize(k)
                    known.remove(k)
                if self.client.metrics["cleared"] == 16:
                    complete = True
                    reason = "upper_bound_16"
                    break
            if not pending and all(not t.seen or t.cleared for t in self.tracks.values()):
                complete = True
                reason = "coverage_and_clearing"
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
