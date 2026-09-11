"""Fetch hash-pinned upstream tools into the ignored local cache."""

from __future__ import annotations

import hashlib
import urllib.parse
import urllib.request

from quality_tools import CACHE, matches_lock, tool_lock


def main() -> int:
    lock = tool_lock()
    if matches_lock(CACHE):
        print("Pinned quality tools are ready.")
        return 0
    for relative, expected in lock["files"].items():
        target = CACHE / relative
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
            continue
        url = (
            f"https://raw.githubusercontent.com/{lock['repository']}/{lock['commit']}/"
            + urllib.parse.quote(relative, safe="/")
        )
        request = urllib.request.Request(url, headers={"User-Agent": "CUMCM-B-reproduction"})
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError(f"Upstream tool hash mismatch: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        print(f"Verified {relative}")
    if not matches_lock(CACHE):
        raise RuntimeError("Quality tool installation is incomplete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
