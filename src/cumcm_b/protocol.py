"""Strict, sequential four-action client. No GUI session-start endpoint exists."""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
import threading
import time
import uuid
from urllib.parse import urlsplit
import requests
import numpy as np


class ProtocolError(RuntimeError):
    pass


class UnresolvedAction(ProtocolError):
    """An action may have executed. No later new action may be sent."""


class BudgetExpired(RuntimeError):
    pass


class HttpTransport:
    def __init__(self, base_url="http://127.0.0.1:2026", retries=3, timeout=3.0):
        parsed = urlsplit(base_url)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in ("127.0.0.1", "localhost", "::1")
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("official client must use an HTTP loopback URL")
        self.base_url = base_url.rstrip("/")
        self.retries = retries
        self.timeout = timeout
        self.session = requests.Session()
        self.session.trust_env = False  # A system proxy must not reroute guest loopback.
        self.uncertain = False

    def __call__(self, endpoint, payload):
        if self.uncertain:
            raise UnresolvedAction(
                "previous action unresolved; restart/resume requires reconciliation"
            )
        body = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        last = None
        for attempt in range(self.retries):
            try:
                response = self.session.post(
                    self.base_url + endpoint,
                    data=body,
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout,
                )
                try:
                    data = response.json()
                except (ValueError, requests.exceptions.JSONDecodeError) as exc:
                    # A response without a valid body does not establish action outcome.
                    last = exc
                    if attempt + 1 < self.retries:
                        time.sleep(0.15 * (attempt + 1))
                    continue
                return response.status_code, data
            except (requests.ConnectionError, requests.Timeout) as exc:
                last = exc
                if attempt + 1 < self.retries:
                    time.sleep(0.15 * (attempt + 1))
        self.uncertain = True
        raise UnresolvedAction(
            f"no definitive response after identical retries: {type(last).__name__}"
        )


class RobotClient:
    """Observable state only. Independent environment truth never enters this class."""

    def __init__(self, transport, robot_id="local", log_path=None, exit_margin=10.0):
        if not robot_id or len(robot_id.encode()) > 64 or any(ord(c) < 32 for c in robot_id):
            raise ValueError("invalid robot_id")
        self.transport = transport
        self.robot_id = robot_id
        self.position = np.zeros(2)
        self.channel = 1
        self.virtual_time = 0.0
        self.limit_virtual = 360000.0
        self.deadline = None
        self.exit_margin = exit_margin
        self.records = []
        self.log_path = Path(log_path) if log_path else None
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            if self.log_path.exists():
                raise FileExistsError(f"refusing to overwrite action log {self.log_path}")
        self.metrics = {
            "distance_m": 0.0,
            "switches": 0,
            "measurements": 0,
            "clear_attempts": 0,
            "cleared": 0,
            "lost_signal": 0,
        }
        self.lock = threading.Lock()
        self.unresolved = False

    def _record(self, record):
        self.records.append(record)
        if self.log_path:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")

    def remaining(self):
        return math.inf if self.deadline is None else self.deadline - time.monotonic()

    def action(self, endpoint, position=None, channel=None):
        if not self.lock.acquire(blocking=False):
            raise ProtocolError("concurrent different actions are forbidden")
        try:
            return self._action(endpoint, position, channel)
        finally:
            self.lock.release()

    def _action(self, endpoint, position, channel):
        if self.unresolved:
            raise UnresolvedAction("client has an unresolved previous action")
        if endpoint not in ("/enter", "/exit", "/measure", "/clear"):
            raise ValueError("unknown endpoint")
        payload = {"arena_id": "default", "robot_id": self.robot_id, "request_id": uuid.uuid4().hex}
        p = self.position.copy()
        distance = 0.0
        switch = 0
        if endpoint in ("/measure", "/clear"):
            p = np.asarray(position, float)
            if p.shape != (2,) or not np.isfinite(p).all() or np.max(np.abs(p)) > 2_000_000:
                raise ValueError("invalid position")
            if (
                isinstance(channel, bool)
                or not isinstance(channel, (int, np.integer))
                or not 1 <= channel <= 20
            ):
                raise ValueError("invalid channel")
            channel = int(channel)
            payload.update(position={"x": float(p[0]), "y": float(p[1])}, channel=channel)
            distance = float(np.linalg.norm(p - self.position))
            switch = int(endpoint == "/measure" and self.channel != channel)
            if (
                self.remaining() < self.exit_margin
                or self.virtual_time + distance / 5 + switch + 5 >= self.limit_virtual
            ):
                raise BudgetExpired("reserve time for a normal exit")
        start = time.monotonic()
        try:
            status, data = self.transport(endpoint, payload)
        except UnresolvedAction:
            self.unresolved = True
            self._record({"endpoint": endpoint, "request": payload, "outcome": "unresolved"})
            raise
        record = {
            "endpoint": endpoint,
            "request": payload,
            "http_status": status,
            "response": copy.deepcopy(data),
        }
        self._record(record)
        if status != 200 or data.get("accepted") is not True:
            # In particular, virtual_time_s=0 in a rejected reply is not a clock reset.
            raise ProtocolError(f"action rejected: HTTP {status}, accepted={data.get('accepted')}")
        clock = data.get("virtual_time_s")
        if (
            isinstance(clock, bool)
            or not isinstance(clock, (int, float))
            or not math.isfinite(clock)
            or clock < self.virtual_time - 1e-5
        ):
            self.unresolved = True
            raise ProtocolError("invalid/non-monotone accepted clock")
        if endpoint == "/enter":
            remaining = data.get("remaining_real_duration_s")
            if (
                isinstance(remaining, bool)
                or not isinstance(remaining, (int, float))
                or not 0 <= remaining <= 1200
            ):
                self.unresolved = True
                raise ProtocolError("missing/invalid remaining_real_duration_s")
            self.deadline = start + remaining
            self.limit_virtual = float(data["max_virtual_duration_s"])
        elif endpoint in ("/measure", "/clear"):
            if endpoint == "/measure":
                result = data.get("measure_result")
                if result not in ("near", "direction", "no_signal"):
                    self.unresolved = True
                    raise ProtocolError("invalid measure result")
                if result == "direction":
                    bearing = data.get("svd_deg")
                    if (
                        isinstance(bearing, bool)
                        or not isinstance(bearing, (int, float))
                        or not math.isfinite(bearing)
                        or not 0 <= bearing < 360
                    ):
                        self.unresolved = True
                        raise ProtocolError("invalid bearing")
                expected = distance / 5 + switch + 5
            else:
                result = data.get("clear_result")
                if result not in ("success", "no_target_in_range"):
                    self.unresolved = True
                    raise ProtocolError("invalid clear result")
                expected = distance / 5 + (5 if result == "success" else 3)
            if abs((clock - self.virtual_time) - expected) > 2e-5:
                self.unresolved = True
                raise ProtocolError("simulator and client timing disagree")
            self.position = p
            self.metrics["distance_m"] += distance
            if endpoint == "/measure":
                self.channel = channel
                self.metrics["switches"] += switch
                self.metrics["measurements"] += 1
                self.metrics["lost_signal"] += int(result == "no_signal")
            else:
                self.metrics["clear_attempts"] += 1
                self.metrics["cleared"] += int(result == "success")
        self.virtual_time = float(clock)
        return data
