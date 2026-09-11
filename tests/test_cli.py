"""CLI checks use fakes only; they never connect to the official simulator."""

import hashlib
import json
import sys
from pathlib import Path

import pytest

from cumcm_b import practice


@pytest.mark.parametrize("extra", [[], ["--robot-id", "example"], ["--practice-ready"]])
def test_practice_requires_id_and_manual_confirmation(monkeypatch, tmp_path, extra):
    monkeypatch.delenv("CUMCM_ROBOT_ID", raising=False)
    output = tmp_path / "private-run"
    monkeypatch.setattr(
        sys, "argv", ["practice", "--question", "4", "--output-dir", str(output), *extra]
    )

    def forbidden(*args, **kwargs):
        pytest.fail("transport must not be constructed without both required confirmations")

    monkeypatch.setattr(practice, "HttpTransport", forbidden)
    with pytest.raises(SystemExit) as caught:
        practice.main()
    assert caught.value.code == 2
    assert not output.exists()


def test_practice_records_installed_sources_without_network(monkeypatch, tmp_path):
    output = tmp_path / "private-run"
    captured = {}
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "practice",
            "--question",
            "4",
            "--robot-id",
            "example",
            "--practice-ready",
            "--output-dir",
            str(output),
        ],
    )
    monkeypatch.setattr(practice, "HttpTransport", lambda *args: object())
    monkeypatch.setattr(practice, "RobotClient", lambda *args, **kwargs: object())

    class FakePolicy:
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)

        def run(self):
            return {"completion_certificate": True, "exit_ok": True, "cleared": 12}

    monkeypatch.setattr(practice, "CoveragePolicy", FakePolicy)
    assert practice.main() == 0
    assert captured["strategy"] == "q4_joint"
    provenance = json.loads((output / "provenance.json").read_text(encoding="utf-8"))
    package = Path(practice.__file__).parent
    assert set(provenance["sha256"]) == {p.name for p in package.glob("*.py")}
    for name, digest in provenance["sha256"].items():
        assert hashlib.sha256((package / name).read_bytes()).hexdigest() == digest
    assert provenance["practice_ready_is_manual_confirmation"] is True
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["total_sources"] is None
    assert summary["scenario_origin"] == "official_practice_user_selected_not_api_verified"
    with pytest.raises(FileExistsError):
        practice.main()


def test_practice_uses_dynamic_q10_for_q3_by_default(monkeypatch, tmp_path):
    output = tmp_path / "q3-run"
    captured = {}
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "practice",
            "--question",
            "3",
            "--robot-id",
            "example",
            "--practice-ready",
            "--output-dir",
            str(output),
        ],
    )
    monkeypatch.setattr(practice, "HttpTransport", lambda *args: object())
    monkeypatch.setattr(practice, "RobotClient", lambda *args, **kwargs: object())

    class FakePolicy:
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)

        def run(self):
            return {"completion_certificate": True, "exit_ok": True, "cleared": 10}

    monkeypatch.setattr(practice, "CoveragePolicy", FakePolicy)
    assert practice.main() == 0
    assert captured["strategy"] == "adaptive_q10_dynamic"
