"""Geometry in metres and degrees. Outer approximations preserve source inclusion."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
import math
import numpy as np
from scipy.optimize import linprog

EPS_DEG = 1.01
TOL = 1e-8


def unit(degrees):
    r = np.deg2rad(degrees)
    return np.array([np.cos(r), np.sin(r)])


def cross(a, b):
    return float(a[0] * b[1] - a[1] * b[0])


def hull(points):
    pts = sorted(set(map(tuple, np.asarray(points, dtype=float).reshape(-1, 2))))
    if len(pts) <= 1:
        return np.asarray(pts, float).reshape(-1, 2)

    def half(seq):
        out = []
        for p in seq:
            while (
                len(out) >= 2
                and cross(np.subtract(out[-1], out[-2]), np.subtract(p, out[-1])) <= 1e-10
            ):
                out.pop()
            out.append(p)
        return out

    return np.asarray(half(pts)[:-1] + half(pts[::-1])[:-1], float)


def wedge_constraints(position, bearing_deg, error_deg=EPS_DEG):
    if not (0 < error_deg < 90):
        raise ValueError("error_deg must be in (0,90)")
    p = np.asarray(position, float)
    lo, hi = unit(bearing_deg - error_deg), unit(bearing_deg + error_deg)
    a = np.array([[lo[1], -lo[0]], [-hi[1], hi[0]]])
    return a, a @ p


def clip(poly, a, b):
    """Clip a convex CCW polygon (or segment/point) to a.x <= b."""
    poly = np.asarray(poly, float).reshape(-1, 2)
    if not len(poly):
        return poly
    # A tiny outward tolerance, never an inward shrink of the feasible set.
    b = float(b) + TOL
    if len(poly) == 1:
        return poly if float(poly[0] @ a) <= b else np.empty((0, 2))
    out = []
    for p, q in zip(poly, np.roll(poly, -1, axis=0)):
        fp, fq = float(p @ a - b), float(q @ a - b)
        pin, qin = fp <= 0, fq <= 0
        if pin:
            out.append(p)
        if pin != qin:
            out.append(p + (q - p) * fp / (fp - fq))
    clean = []
    for p in out:
        if not clean or np.linalg.norm(p - clean[-1]) > 1e-9:
            clean.append(p)
    if len(clean) > 1 and np.linalg.norm(clean[0] - clean[-1]) <= 1e-9:
        clean.pop()
    return np.asarray(clean, float).reshape(-1, 2)


def disk_outer(center=(0, 0), radius=1800.0, sides=128):
    theta = (np.arange(sides) + 0.5) * 2 * np.pi / sides
    return np.asarray(center) + radius / math.cos(math.pi / sides) * np.column_stack(
        (np.cos(theta), np.sin(theta))
    )


def clip_disk_outer(poly, center, radius, sides=128):
    theta = np.arange(sides) * 2 * np.pi / sides
    normals = np.column_stack((np.cos(theta), np.sin(theta)))
    if not len(poly):
        return poly
    # Constraints already satisfied by every vertex require no clipping.
    active = np.max((poly - np.asarray(center)) @ normals.T, axis=0) > radius
    for a in normals[active]:
        poly = clip(poly, a, radius + a @ center)
    return poly


def area(poly):
    if len(poly) < 3:
        return 0.0
    return (
        abs(
            float(
                np.sum(poly[:, 0] * np.roll(poly[:, 1], -1) - poly[:, 1] * np.roll(poly[:, 0], -1))
            )
        )
        / 2
    )


def halfplane_intersection(a, b):
    """Explicit EMPTY/UNBOUNDED/BOUNDED; no artificial bounding square."""
    a, b = np.asarray(a, float).reshape(-1, 2), np.asarray(b, float)
    if not len(a):
        return {"status": "UNBOUNDED", "vertices": np.empty((0, 2)), "diameter_m": math.inf}
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("nonfinite constraints")
    kwargs = dict(A_ub=a, b_ub=b, bounds=[(None, None)] * 2, method="highs")
    feasible = linprog([0.0, 0.0], **kwargs)
    if feasible.status == 2:
        return {"status": "EMPTY", "vertices": np.empty((0, 2)), "diameter_m": None}
    if not feasible.success:
        raise ArithmeticError(feasible.message)
    for obj in ([1, 0], [-1, 0], [0, 1], [0, -1]):
        result = linprog(obj, **kwargs)
        if result.status == 3:
            return {"status": "UNBOUNDED", "vertices": np.empty((0, 2)), "diameter_m": math.inf}
        if not result.success:
            raise ArithmeticError(result.message)
    pts = []
    for i, j in combinations(range(len(a)), 2):
        mat = a[[i, j]]
        if abs(np.linalg.det(mat)) <= 1e-13:
            continue
        p = np.linalg.solve(mat, b[[i, j]])
        if np.all(a @ p <= b + 1e-7):
            pts.append(p)
    if not pts:
        raise ArithmeticError("bounded feasible set without recoverable vertices")
    poly = hull(pts)
    d, pair = diameter(poly)
    return {"status": "BOUNDED", "vertices": poly, "diameter_m": d, "diameter_pair": pair}


def bearing_intersection(observations, error_deg=1.0):
    constraints = [wedge_constraints(p, t, error_deg) for p, t in observations]
    if not constraints:
        return halfplane_intersection([], [])
    return halfplane_intersection(
        np.concatenate([x[0] for x in constraints]), np.concatenate([x[1] for x in constraints])
    )


def diameter(poly):
    """Rotating calipers on an ordered convex hull; ties include both antipodes."""
    poly = np.asarray(poly, float)
    n = len(poly)
    if not n:
        raise ValueError("empty diameter")
    if n == 1:
        return 0.0, poly[[0, 0]]
    if n == 2:
        return float(np.linalg.norm(poly[1] - poly[0])), poly.copy()
    best, pair, j = -1.0, None, 1

    def twice_area(i, k):
        return abs(cross(poly[(i + 1) % n] - poly[i], poly[k] - poly[i]))

    for i in range(n):
        for _ in range(n):
            nj = (j + 1) % n
            if twice_area(i, nj) > twice_area(i, j) + 1e-10:
                j = nj
            else:
                break
        js = [j]
        if abs(twice_area(i, (j + 1) % n) - twice_area(i, j)) <= 1e-10:
            js.append((j + 1) % n)
        for k in (i, (i + 1) % n):
            for jj in js:
                d2 = float(np.sum((poly[k] - poly[jj]) ** 2))
                if d2 > best:
                    best, pair = d2, poly[[k, jj]]
    return math.sqrt(best), pair


def diameter_bruteforce(poly):
    return float(np.sqrt(np.max(np.sum((poly[:, None, :] - poly[None, :, :]) ** 2, axis=-1))))


def _circle3(p, q, r):
    u, v = q - p, r - p
    det = cross(u, v)
    if abs(det) <= 1e-12 * max(1.0, np.linalg.norm(u) * np.linalg.norm(v)):
        candidates = []
        for a, b in ((p, q), (p, r), (q, r)):
            c = (a + b) / 2
            rr = float(np.linalg.norm(a - b) / 2)
            if max(np.linalg.norm(z - c) for z in (p, q, r)) <= rr + 1e-7:
                candidates.append((rr, c))
        if not candidates:
            raise ArithmeticError("unstable circumcircle")
        rr, c = min(candidates, key=lambda x: x[0])
        return c, rr
    uu, vv = float(u @ u), float(v @ v)
    c = p + np.array([v[1] * uu - u[1] * vv, u[0] * vv - v[0] * uu]) / (2 * det)
    return c, float(np.linalg.norm(c - p))


def enclosing_circle(points, seed=20260911):
    """Randomized incremental smallest circle, then independently check containment."""
    pts = np.asarray(points, float).reshape(-1, 2)
    if not len(pts):
        raise ValueError("empty enclosing circle")
    pts = pts[np.random.default_rng(seed).permutation(len(pts))]
    c, rad = pts[0].copy(), 0.0

    def outside(p):
        return np.linalg.norm(p - c) > rad + 1e-8

    for i, p in enumerate(pts):
        if outside(p):
            c, rad = p.copy(), 0.0
            for j, q in enumerate(pts[:i]):
                if outside(q):
                    c, rad = (p + q) / 2, float(np.linalg.norm(p - q) / 2)
                    for r in pts[:j]:
                        if outside(r):
                            c, rad = _circle3(p, q, r)
    required = float(np.max(np.linalg.norm(pts - c, axis=1)))
    if required > rad + 1e-5:
        raise ArithmeticError("minimum circle containment failed")
    return c, max(rad, required)


@dataclass
class Belief:
    polygon: np.ndarray = field(default_factory=disk_outer)
    observations: list = field(default_factory=list)
    history: list = field(default_factory=list)
    error_deg: float = EPS_DEG

    def observe(self, position, bearing):
        p = np.asarray(position, float)
        a, b = wedge_constraints(p, bearing, self.error_deg)
        for aa, bb in zip(a, b):
            self.polygon = clip(self.polygon, aa, bb)
        self.polygon = clip_disk_outer(self.polygon, p, 1500.0)
        if not len(self.polygon):
            raise ArithmeticError("inconsistent observations: empty outer feasible set")
        if not any(np.linalg.norm(p - old[0]) < 1e-7 for old in self.observations):
            self.observations.append((p.copy(), float(bearing)))
        c, r = enclosing_circle(self.polygon)
        self.history.append(
            {
                "observations": len(self.observations),
                "area_m2": area(self.polygon),
                "radius_m": r,
                "center": c.tolist(),
                "polygon": self.polygon.tolist(),
            }
        )


def candidate_points(
    belief, current, travel_weight=0.02, objective="worst", angle_step=22.5
):
    """Conservative reception filtering; deterministic geometry/travel ranking."""
    if not (0 < angle_step <= 90):
        raise ValueError("angle_step must be in (0, 90]")
    poly = belief.polygon
    c, rad = enclosing_circle(poly)
    if not belief.observations:
        return []
    frame = belief.observations[0][1]
    candidates = [c]
    for radius in (40.0, 80.0, 160.0, 320.0, 500.0, 650.0):
        for ang in np.arange(0, 360, angle_step) + frame:
            candidates.append(c + radius * unit(ang))
    old = np.array([p for p, t in belief.observations])
    scenarios = np.vstack((poly, (poly + np.roll(poly, -1, axis=0)) / 2, c))
    # A normal direction observation rules out distance <= 5m at every old point.
    # Keep the outer polygon unchanged for guarantees, but never score its artificial
    # apex as a possible normal-bearing source. Add valid near-boundary samples.
    near_samples = []
    for p in old:
        for v in poly:
            delta = v - p
            distance = np.linalg.norm(delta)
            if distance > 5.01:
                g = p + delta * (5.01 / distance)
                if all(
                    cross(b - a, g - a) >= -1e-7 for a, b in zip(poly, np.roll(poly, -1, axis=0))
                ):
                    near_samples.append(g)
    if near_samples:
        scenarios = np.vstack((scenarios, near_samples))
    valid = np.all(
        np.sum((scenarios[:, None, :] - old[None, :, :]) ** 2, axis=2) > 25.0 + 1e-10, axis=1
    )
    scenarios = scenarios[valid]
    if not len(scenarios):
        return []
    results = []
    for q in candidates:
        if np.max(np.linalg.norm(poly - q, axis=1)) > 999.99:
            continue
        if np.min(np.linalg.norm(old - q, axis=1)) < 1.0:
            continue
        pos = np.vstack((old, q))
        diff = scenarios[:, None, :] - pos[None, :, :]
        d2 = np.sum(diff**2, axis=2)
        near = d2[:, -1] <= 25.0
        # Only the proposed observation may be near; its score is replaced below.
        d2 = np.where(d2 > 0, d2, 1.0)
        h = np.stack((-diff[:, :, 1], diff[:, :, 0]), axis=2) / d2[:, :, None]
        gram = np.einsum("sni,snj->sij", h, h)
        eig = np.linalg.eigvalsh(gram)
        regular = eig[:, 0] > np.maximum(1e-20, eig[:, 1] / 1e12)
        uncertainty = np.full(len(scenarios), np.inf)
        if regular.any():
            inverse = np.linalg.inv(gram[regular])
            hp = np.einsum("sij,snj->sin", inverse, h[regular])
            uncertainty[regular] = np.deg2rad(belief.error_deg) * np.sum(
                np.linalg.norm(hp, axis=1), axis=1
            )
        uncertainty[near] = 5.0
        worst = float(np.max(uncertainty))
        finite = uncertainty[np.isfinite(uncertainty)]
        q10 = float(np.quantile(finite, 0.10)) if len(finite) else math.inf
        q25 = float(np.quantile(finite, 0.25)) if len(finite) else math.inf
        median = float(np.median(finite)) if len(finite) else math.inf
        p90 = float(np.quantile(finite, 0.90)) if len(finite) else math.inf
        distance = float(np.linalg.norm(q - current))
        if np.isfinite(worst):
            geometric = {"worst": worst, "p90": p90, "q10": q10, "q25": q25, "median": median}.get(
                objective
            )
            if geometric is None:
                raise ValueError("objective must be worst, p90, q25, q10, or median")
            results.append(
                {
                    "position": q,
                    "worst_linearized_m": worst,
                    "p90_linearized_m": p90,
                    "median_linearized_m": median,
                    "q25_linearized_m": q25,
                    "q10_linearized_m": q10,
                    "distance_m": distance,
                    "score": geometric + travel_weight * distance,
                    "max_source_distance_m": float(np.max(np.linalg.norm(poly - q, axis=1))),
                }
            )
    return sorted(results, key=lambda x: x["score"])


def optical_cover_points(belief, step=25.0):
    """Every intersecting closed cell is retained, including thin/degenerate regions."""
    from shapely.geometry import Polygon, LineString, Point, box

    if not (0 < step < 20 * math.sqrt(2)):
        raise ValueError("grid step must guarantee a strict sub-20m covering radius")
    angle = belief.observations[0][1]
    u = unit(angle)
    basis = np.array([u, [-u[1], u[0]]])
    origin = belief.observations[0][0]
    local = (belief.polygon - origin) @ basis.T
    if len(local) >= 3 and area(local) > 1e-12:
        shape = Polygon(local)
    elif len(local) >= 2:
        shape = LineString(local)
    else:
        shape = Point(local[0])
    shape = shape.buffer(1e-7)
    lo = np.floor(np.min(local, axis=0) / step).astype(int) - 1
    hi = np.floor(np.max(local, axis=0) / step).astype(int) + 1
    points = []
    for i in range(lo[0], hi[0] + 1):
        for j in range(lo[1], hi[1] + 1):
            if shape.intersects(box(i * step, j * step, (i + 1) * step, (j + 1) * step)):
                p = np.array([(i + 0.5) * step, (j + 0.5) * step]) @ basis + origin
                points.append(p)
    return np.asarray(points)
