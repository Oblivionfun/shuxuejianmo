"""Documented LOCAL environment, not a reconstruction of official hidden cases."""

from __future__ import annotations

from dataclasses import dataclass, asdict
import copy
import hashlib
import json
import math
import time
import numpy as np
from .geometry import unit


@dataclass(frozen=True)
class Source:
    channel: int
    x: float
    y: float
    radius: float
    orientation: float | None = None

    @property
    def position(self):
        return np.array([self.x, self.y])


def generate_sources(seed, question=3, count=None, stress=None):
    rng = np.random.default_rng(seed)
    count = int(rng.integers(10, 17)) if count is None else count
    if not 10 <= count <= 16:
        raise ValueError("source count must be 10..16")
    channels = rng.choice(np.arange(1, 21), size=count, replace=False)
    angles = rng.uniform(0, 360, count)
    distances = 1800 * np.sqrt(rng.random(count))
    if stress == "outward_boundary":
        distances[:] = 1800.0
        angles = np.arange(count) * 360 / count + 7.5
    sources = []
    for i in range(count):
        p = unit(angles[i]) * distances[i]
        orientation = None
        if question == 4 and (i % 2 == 0 or stress == "outward_boundary"):
            orientation = float(angles[i] if stress == "outward_boundary" else rng.uniform(0, 360))
        radius = float(1000.0 if stress else rng.uniform(1000, 1500))
        sources.append(Source(int(channels[i]), float(p[0]), float(p[1]), radius, orientation))
    return sources


class SyntheticArena:
    """Only process() is given to the policy; truth is used solely by evaluator."""

    def __init__(self, sources, seed=0, error_mode="fixed_location", robot_id="local"):
        self.sources = {s.channel: s for s in sources}
        self.seed = seed
        self.error_mode = error_mode
        self.robot_id = robot_id
        self.position = np.zeros(2)
        self.channel = 1
        self.virtual = 0.0
        self.active = False
        self.entered = False
        self.cleared = set()
        self.cache = {}

    def _noise(self, channel, p):
        if self.error_mode == "positive":
            return 1.0
        if self.error_mode == "negative":
            return -1.0
        if self.error_mode == "zero":
            return 0.0
        if self.error_mode == "spatial":
            return math.sin(p[0] / 83 + p[1] / 117 + channel + self.seed)
        raw = f"{self.seed}:{channel}:{float(p[0]).hex()}:{float(p[1]).hex()}".encode()
        integer = int.from_bytes(hashlib.blake2b(raw, digest_size=8).digest(), "big")
        return 2 * (integer / (2**64 - 1)) - 1

    def process(self, endpoint, payload):
        identity = payload.get("request_id")
        encoded = json.dumps(
            [endpoint, payload], sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        reject = {
            "accepted": False,
            "real_timestamp_ms": int(time.time() * 1000),
            "virtual_time_s": 0,
        }
        if identity in self.cache:
            original, response = self.cache[identity]
            return (200, copy.deepcopy(response)) if encoded == original else (409, reject)
        expected = {"arena_id", "robot_id", "request_id"}
        if endpoint in ("/measure", "/clear"):
            expected |= {"position", "channel"}
        if (
            set(payload) != expected
            or payload.get("arena_id") != "default"
            or payload.get("robot_id") != self.robot_id
        ):
            return 200, reject
        if endpoint == "/enter":
            if self.entered:
                return 200, reject
            self.active = True
            self.entered = True
            extra = {
                "max_virtual_duration_s": 360000,
                "max_real_duration_s": 1200,
                "remaining_real_duration_s": 1200,
            }
        elif not self.active:
            return 200, reject
        elif endpoint == "/exit":
            self.active = False
            extra = {"exit_reason": "user_exit"}
        else:
            if endpoint not in ("/measure", "/clear"):
                return 404, reject
            p = np.array([payload["position"]["x"], payload["position"]["y"]], float)
            channel = payload["channel"]
            if not np.isfinite(p).all() or np.max(np.abs(p)) > 2e6 or not 1 <= channel <= 20:
                return 400, reject
            distance = float(np.linalg.norm(p - self.position))
            self.virtual += distance / 5
            self.position = p
            source = self.sources.get(channel)
            source = None if channel in self.cleared else source
            r = math.inf if source is None else float(np.linalg.norm(source.position - p))
            if endpoint == "/clear":
                success = r <= 20
                self.virtual += 5 if success else 3
                if success:
                    self.cleared.add(channel)
                extra = {"clear_result": "success" if success else "no_target_in_range"}
            else:
                self.virtual += 5 + int(self.channel != channel)
                self.channel = channel
                visible = source is not None and r <= source.radius + 1e-10
                if visible and source.orientation is not None:
                    visible = float((p - source.position) @ unit(source.orientation)) >= -1e-9
                if not visible:
                    extra = {"measure_result": "no_signal"}
                elif r <= 5:
                    extra = {"measure_result": "near"}
                else:
                    delta = source.position - p
                    bearing = (
                        math.degrees(math.atan2(delta[1], delta[0])) + self._noise(channel, p)
                    ) % 360
                    extra = {"measure_result": "direction", "svd_deg": round(bearing, 2) % 360}
        response = {
            "accepted": True,
            "real_timestamp_ms": int(time.time() * 1000),
            "virtual_time_s": round(self.virtual, 6),
            **extra,
        }
        self.cache[identity] = (encoded, copy.deepcopy(response))
        return 200, response


def source_rows(sources):
    return [asdict(s) for s in sources]
