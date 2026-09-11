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


Q4_TRIANGLE_SIDE_M = 995.0
Q4_TRIANGLE_OFFSET = (0.23, 0.90)
Q4_TRIANGULAR_ROUTE_ORDER = (
    0,
    16,
    17,
    21,
    20,
    15,
    9,
    10,
    11,
    5,
    2,
    1,
    4,
    3,
    8,
    14,
    19,
    23,
    24,
    25,
    22,
    18,
    13,
    12,
    7,
    6,
)


@lru_cache(maxsize=4)
def _triangular_geometry(side=Q4_TRIANGLE_SIDE_M, offset=Q4_TRIANGLE_OFFSET):
    """Build a closed triangular-cell cover with a conservative disk boundary."""
    side = float(side)
    ox, oy = map(float, offset)

    def xy(i, j):
        return np.array(
            [side * (i + ox + (j + oy) / 2), side * math.sqrt(3) / 2 * (j + oy)]
        )

    keys = set()
    cells = []
    for i in range(-8, 9):
        for j in range(-8, 9):
            for ids in (((i, j), (i + 1, j), (i, j + 1)), ((i + 1, j), (i + 1, j + 1), (i, j + 1))):
                tri = np.array([xy(*ij) for ij in ids])
                if Polygon(tri).distance(Point(0, 0)) <= 1800 + 1e-8:
                    keys.update(ids)
                    cells.append(tri)
    # Lexicographic lattice order is stable across the optimized and legacy
    # constructions, so the deterministic route indices remain auditable.
    ordered = sorted(keys)
    return np.vstack((np.zeros(2), [xy(*ij) for ij in ordered])), np.array(cells)


def triangular_cover():
    points, cells = _triangular_geometry()
    return points.copy(), cells.copy()


def legacy_triangular_cover():
    """Return the former 950 m construction for historical reproduction."""
    points, cells = _triangular_geometry(950.0, (1 / 3, 1 / 3))
    return points.copy(), cells.copy()


def q4_station_route(points):
    """Return the deterministic open route used by the optimized triangular q4 policy."""
    points = np.asarray(points, float)
    if len(points) == len(Q4_TRIANGULAR_ROUTE_ORDER):
        return points[list(Q4_TRIANGULAR_ROUTE_ORDER)].copy()
    return points.copy()


def stations(question, coverage="triangular"):
    if question == 3:
        return np.vstack((np.zeros(2), [900 * math.sqrt(3) * unit(t) for t in range(0, 360, 60)]))
    if question == 4:
        if coverage == "triangular":
            return triangular_cover()[0]
        if coverage == "triangular_legacy":
            return legacy_triangular_cover()[0]
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
        known_measure_budget=4,
        localize_threshold_m=300.0,
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
            "q4_joint",
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
        self.known_measure_budget = int(known_measure_budget)
        self.localize_threshold_m = float(localize_threshold_m)
        if self.known_measure_budget < 0:
            raise ValueError("known_measure_budget must be nonnegative")
        if self.localize_threshold_m < 0:
            raise ValueError("localize_threshold_m must be nonnegative")
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
                "q4_joint": "worst",
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
                    if self.strategy in {
                        "adaptive_q25_fine",
                        "adaptive_q10_dynamic_fine",
                    }
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

    def _station_channels(self):
        """Choose feedback queries without weakening the q4 coverage certificate."""
        if self.strategy != "q4_joint":
            return [k for k, t in self.tracks.items() if not t.cleared]
        unseen = [k for k, t in self.tracks.items() if not t.seen and not t.cleared]
        known = [k for k, t in self.tracks.items() if t.seen and not t.cleared]
        known.sort(key=lambda k: -enclosing_circle(self.tracks[k].belief.polygon)[1])
        return unseen + known[: self.known_measure_budget]

    def _localize_nearby(self):
        """Clear a discovered target when its certified center is near the route."""
        if self.strategy != "q4_joint":
            return
        while True:
            candidates = []
            for k, track in self.tracks.items():
                if not track.seen or track.cleared:
                    continue
                center, _ = enclosing_circle(track.belief.polygon)
                distance = float(np.linalg.norm(center - self.client.position))
                if distance <= self.localize_threshold_m:
                    candidates.append((distance, k))
            if not candidates:
                return
            _, channel = min(candidates)
            self.localize(channel)

    def run(self):
        started = time.monotonic()
        self.client.action("/enter")
        points = stations(self.question, self.coverage)
        if self.strategy == "q4_joint" and self.question == 4 and self.coverage == "triangular":
            points = q4_station_route(points)
        pending = list(range(len(points)))
        complete = False
        reason = "not_started"
        try:
            while pending:
                index = (
                    pending[0]
                    if self.strategy in {"fixed", "q4_joint"}
                    else min(
                        pending, key=lambda i: np.linalg.norm(points[i] - self.client.position)
                    )
                )
                p = points[index]
                channels = self._station_channels()
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
                self._localize_nearby()
                if self.client.metrics["cleared"] == 16:
                    complete = True
                    reason = "upper_bound_16"
                    break
                if self.strategy != "q4_joint":
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
            if self.strategy == "q4_joint":
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
