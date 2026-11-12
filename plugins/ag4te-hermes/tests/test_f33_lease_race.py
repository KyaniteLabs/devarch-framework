"""F33: two processes breaking the same stale dig lease never both win."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parent.parent
ROUNDS = 100

CHILD = r"""
import importlib.util, sys, time, os
pkg, base, t0, rounds, label = sys.argv[1], sys.argv[2], float(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
spec = importlib.util.spec_from_file_location("ag4te_f33_child", os.path.join(pkg, "__init__.py"))
ag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ag)
_orig = ag.read_lease
def _slow_read(*a, **kw):  # widen the window between judging a lease stale and acting on it
    res = _orig(*a, **kw)
    time.sleep(0.02)
    return res
ag.read_lease = _slow_read
for r in range(rounds):
    while time.time() < t0 + r * 0.15:
        pass
    settings = {"data_dir": os.path.join(base, str(r))}
    try:
        with ag._jobs_lock:
            ag._take_lease(label + str(r), settings)
        print(r, "WIN", flush=True)
    except ag.DigError:
        print(r, "LOSE", flush=True)
time.sleep(float(os.environ.get("HOLD", "2")))  # winners stay alive, so their leases stay live
"""


def _dead_pid():
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


@pytest.mark.skipif(os.name == "nt", reason="POSIX pid and timing semantics")
def test_two_processes_breaking_a_stale_lease_have_exactly_one_winner(tmp_path):
    import socket

    dead = _dead_pid()
    for r in range(ROUNDS):
        d = tmp_path / str(r)
        d.mkdir()
        (d / "dig.lease").write_text(
            json.dumps(
                {"project": "old", "pid": dead, "host": socket.gethostname(), "since": time.time()}
            )
        )
    t0 = time.time() + 1.5
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", CHILD, str(PKG), str(tmp_path), str(t0), str(ROUNDS), lab],
            stdout=subprocess.PIPE,
            text=True,
        )
        for lab in ("a", "b")
    ]
    results = []
    for p in procs:
        out, _ = p.communicate(timeout=120)
        results.append(dict(line.split() for line in out.splitlines() if line.strip()))
    assert p.returncode == 0
    bad = {
        r: (results[0].get(str(r)), results[1].get(str(r)))
        for r in range(ROUNDS)
        if sorted([results[0].get(str(r), "?"), results[1].get(str(r), "?")]) != ["LOSE", "WIN"]
    }
    assert not bad, f"rounds without exactly one winner: {bad}"
