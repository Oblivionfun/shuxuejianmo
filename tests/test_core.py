import copy
import itertools
import math
import numpy as np
import pytest
from cumcm_b.geometry import (
    bearing_intersection,
    enclosing_circle,
    hull,
    diameter,
    diameter_bruteforce,
    Belief,
    candidate_points,
    optical_cover_points,
    unit,
    halfplane_intersection,
)
from cumcm_b.synthetic import Source, SyntheticArena, generate_sources
from cumcm_b.protocol import RobotClient, ProtocolError, HttpTransport
from cumcm_b.policy import CoveragePolicy, stations, triangular_cover


def triangle_observations(side=39.0):
    verts = np.array([[0, 0], [side, 0], [side / 2, side * math.sqrt(3) / 2]])
    obs = []
    for p, q in zip(verts, np.roll(verts, -1, axis=0)):
        e = (q - p) / np.linalg.norm(q - p)
        obs.append((p - 1200 * e, (math.degrees(math.atan2(e[1], e[0])) + 1) % 360))
    return verts, obs


def test_triangle_is_realizable_and_diameter_circle_fails():
    verts, obs = triangle_observations()
    result = bearing_intersection(obs)
    assert result["status"] == "BOUNDED"
    assert result["diameter_m"] == pytest.approx(39, abs=1e-6)
    c, r = enclosing_circle(result["vertices"])
    assert r == pytest.approx(39 / math.sqrt(3), abs=1e-6)
    assert r > 20 and result["diameter_m"] < 40
    truth = verts.mean(axis=0)
    for p, bearing in obs:
        actual = math.degrees(math.atan2(*(truth - p)[::-1])) % 360
        assert abs((actual - bearing + 180) % 360 - 180) <= 1
        assert np.linalg.norm(truth - p) <= 1500


def test_empty_unbounded_segment_point():
    assert halfplane_intersection([[1, 0], [-1, 0]], [0, -1])["status"] == "EMPTY"
    assert bearing_intersection([((0, 0), 0)])["status"] == "UNBOUNDED"
    a = [[1, 0], [-1, 0], [0, 1], [0, -1]]
    line = halfplane_intersection(a, [0, 0, 1, 0])
    assert line["diameter_m"] == pytest.approx(1)
    point = halfplane_intersection(a, [0, 0, 0, 0])
    assert point["diameter_m"] == pytest.approx(0)


def test_calipers_random_and_circle_oracle():
    rng = np.random.default_rng(991)
    for _ in range(50):
        pts = hull(rng.normal(size=(12, 2)) * 100)
        assert diameter(pts)[0] == pytest.approx(diameter_bruteforce(pts), abs=1e-7)
        c, r = enclosing_circle(pts)
        assert np.max(np.linalg.norm(pts - c, axis=1)) <= r + 1e-7
        # Independent support enumeration via a linear system, not _circle3.
        candidates = [(pts[i] + pts[j]) / 2 for i, j in itertools.combinations(range(len(pts)), 2)]
        for i, j, k in itertools.combinations(range(len(pts)), 3):
            mat = 2 * np.array([pts[j] - pts[i], pts[k] - pts[i]])
            if abs(np.linalg.det(mat)) > 1e-8:
                rhs = np.array(
                    [pts[j] @ pts[j] - pts[i] @ pts[i], pts[k] @ pts[k] - pts[i] @ pts[i]]
                )
                candidates.append(np.linalg.solve(mat, rhs))
        oracle = min(max(np.linalg.norm(pts - x, axis=1)) for x in candidates)
        assert r == pytest.approx(oracle, rel=1e-7, abs=1e-7)


def test_wrapped_bearing_contains_truth_and_optical_cells_cover():
    for deg in (0, 359.99, 90, 180):
        b = Belief()
        b.observe([0, 0], deg)
        cells = optical_cover_points(b)
        for delta in (-1.005, 0, 1.005):
            for r in (5.01, 100, 1000, 1499.99):
                g = r * unit(deg + delta)
                assert np.min(np.linalg.norm(cells - g, axis=1)) < 20
        q = candidate_points(b, np.zeros(2))
        assert q and np.isfinite(q[0]["score"])
        assert all(x["max_source_distance_m"] <= 1000 for x in q)


def test_station_certificates():
    rng = np.random.default_rng(554)
    pts = (
        1800
        * np.sqrt(rng.random(1000))[:, None]
        * np.array([unit(x) for x in rng.uniform(0, 360, 1000)])
    )
    boundary = np.array([1800 * unit(x) for x in np.linspace(0, 360, 1441)])
    pts = np.vstack((pts, boundary))
    assert (
        np.max(np.min(np.linalg.norm(pts[:, None, :] - stations(3), axis=2), axis=1)) <= 900 + 1e-8
    )
    for g in pts[::4]:
        near = stations(4)[np.linalg.norm(stations(4) - g, axis=1) <= 1000]
        for theta in (0, 31, 90, 167, 220, 300):
            assert np.max((near - g) @ unit(theta)) >= -1e-8


def test_triangular_cover_is_a_continuous_disk_certificate():
    from shapely.geometry import Polygon, Point, MultiPoint
    from shapely.ops import unary_union

    points, cells = triangular_cover()
    assert len(points) == 28 and len(cells) == 37
    cover = unary_union([Polygon(t) for t in cells])
    assert cover.contains(Point(0, 0))
    # Any exit from the union crosses a boundary >=1800m away: entire closed disk is covered.
    assert cover.boundary.distance(Point(0, 0)) >= 1800 - 1e-7
    for tri in cells:
        assert np.max(np.linalg.norm(tri[:, None, :] - tri[None, :, :], axis=2)) <= 950 + 1e-7
        assert all(np.min(np.linalg.norm(points - p, axis=1)) < 1e-8 for p in tri)
    for g in [*points, *[1800 * unit(t) for t in np.linspace(0, 360, 721)]]:
        if np.linalg.norm(g) > 1800 + 1e-7:
            continue
        near = points[np.linalg.norm(points - g, axis=1) <= 1000]
        # Independent all-orientation check, rather than checking a few sampled emission angles.
        assert MultiPoint(near).convex_hull.buffer(1e-7).covers(Point(g))


def test_q2_apex_perturbation_does_not_dominate_score():
    scores = []
    for delta in (0.0, -1e-7, -1e-6):
        b = Belief()
        w = 1500 * math.tan(math.radians(1.01))
        b.polygon = hull([[delta, 0], [1500, -w], [1500, w]])
        b.observations = [(np.zeros(2), 0.0)]
        rows = candidate_points(b, np.zeros(2))
        assert rows and rows[0]["worst_linearized_m"] < 200
        scores.append(rows[0]["worst_linearized_m"])
    assert max(scores) - min(scores) < 1e-3


def test_state_clock_and_idempotency():
    source = Source(2, 300, 0, 1000)
    arena = SyntheticArena([source], error_mode="zero")
    client = RobotClient(arena.process)
    client.action("/enter")
    client.action("/measure", [0, 0], 2)
    assert client.channel == 2 and client.virtual_time == 6
    client.action("/clear", [300, 0], 2)
    assert client.virtual_time == 71 and client.channel == 2
    client.action("/clear", [300, 0], 3)
    assert client.virtual_time == 74 and client.channel == 2
    last = client.records[-1]
    status, response = arena.process(last["endpoint"], last["request"])
    assert status == 200 and response == last["response"] and arena.virtual == 74
    changed = copy.deepcopy(last["request"])
    changed["channel"] = 4
    assert arena.process("/clear", changed)[0] == 409
    virtual = client.virtual_time
    pos = client.position.copy()
    client.transport = lambda ep, p: (
        200,
        {"accepted": False, "virtual_time_s": 0, "real_timestamp_ms": 0},
    )
    with pytest.raises(ProtocolError):
        client.action("/measure", [900, 200], 4)
    assert (
        client.virtual_time == virtual
        and np.array_equal(client.position, pos)
        and client.channel == 2
    )


def test_http_transport_exact_retry():
    import requests

    class Response:
        status_code = 200

        def json(self):
            return {"accepted": True, "virtual_time_s": 6, "real_timestamp_ms": 0}

    class Fake:
        def __init__(self):
            self.bodies = []

        def post(self, url, **kw):
            self.bodies.append((url, kw["data"]))
            if len(self.bodies) == 1:
                raise requests.Timeout("lost response")
            return Response()

    transport = HttpTransport(retries=2)
    transport.session = Fake()
    payload = {"request_id": "constant"}
    assert transport("/measure", payload)[0] == 200
    assert transport.session.bodies[0] == transport.session.bodies[1]


def test_candidate_quantile_objectives_are_explicit():
    belief = Belief()
    belief.observe([0, 0], 0)
    rows = candidate_points(belief, np.zeros(2), objective="q25")
    assert rows
    assert all("q25_linearized_m" in row and "worst_linearized_m" in row for row in rows)
    assert rows[0]["score"] <= rows[-1]["score"]
    with pytest.raises(ValueError, match="objective"):
        candidate_points(belief, np.zeros(2), objective="unknown")


@pytest.mark.parametrize("question", [3, 4])
def test_complete_synthetic_case(question):
    sources = generate_sources(20260911, question, count=10)
    arena = SyntheticArena(sources, seed=20260911)
    client = RobotClient(arena.process)
    result = CoveragePolicy(client, question).run()
    assert result["completion_certificate"], result
    assert result["exit_ok"] and result["cleared"] == len(sources)
    assert result["virtual_time_s"] < 360000
    assert result["virtual_time_s"] == pytest.approx(
        result["distance_m"] / 5
        + result["switches"]
        + 5 * result["measurements"]
        + 3 * result["clear_attempts"]
        + 2 * result["cleared"],
        abs=1e-5,
    )


def test_dynamic_q10_strategy_is_certificate_safe():
    sources = generate_sources(20261011, question=3, count=10)
    arena = SyntheticArena(sources, seed=20261011)
    result = CoveragePolicy(
        RobotClient(arena.process), question=3, strategy="adaptive_q10_dynamic", travel_weight=0.02
    ).run()
    assert result["completion_certificate"] and result["exit_ok"]
    assert result["fallback_actions"] == 0
