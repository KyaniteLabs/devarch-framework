"""The agate stone's colour semantics, checked on the pure layout in desktop/plugin.js.

P1 share: inside each era, each kind's band thickness equals its share of the era's commits.
P2 time: commits are laid oldest at the rim side to newest at the core side (chunk order).
P3 legibility: no time chunk is thinner than 3px unless it is a single commit.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1] / "desktop" / "plugin.js"
RAD, CORE = 104, 0.17

HARNESS = r"""
%(kinds)s
%(layout)s
const cases = JSON.parse(require('fs').readFileSync(0, 'utf8'))
const out = cases.map(d => stoneLayout(d, %(rad)s, %(core)s).map(e => ({ f0: e.f0, f1: e.f1, chunks: e.chunks, n: e.n,
  runs: e.runs.map(r => ({ j: r.j, n: r.n, g0: r.g0, g1: r.g1, per: r.per })) })))
process.stdout.write(JSON.stringify(out))
"""

KINDS = ["feat", "fix", "refactor", "docs", "ops", "test", "other"]


def _layout(cases):
    src = PLUGIN.read_text()
    kinds = re.search(r"^const KINDS = .*$", src, re.M).group(0)
    block = re.search(r"// stone-layout:start.*?// stone-layout:end", src, re.S).group(0)
    js = HARNESS % {"kinds": kinds, "layout": block, "rad": RAD, "core": CORE}
    res = subprocess.run(["node", "-e", js], input=json.dumps(cases), capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


def _day(d, k):
    return {"d": d, "n": sum(k), "k": k}


def _commit(day, hh, kind):
    return {"day": day, "t": f"{day}T{hh:02d}:00:00-08:00", "kind": kind}


def _cases():
    # 1. one small era with exact commit order: feat, feat, fix, docs, other x3
    small = {
        "project": "small",
        "days": [_day("2026-01-01", [2, 1, 0, 1, 0, 0, 3])],
        "commits": [_commit("2026-01-01", h, k) for h, k in
                    enumerate(["feat", "feat", "fix", "docs", "other", "other", "other"])],
        "clusters": [{"start": "2026-01-01", "end": "2026-01-01", "commits": 7, "k": [2, 1, 0, 1, 0, 0, 3]}],
    }
    # 2. a big era: 400 days, first half all feat, second half all fix (no commit list)
    days = [_day(f"2025-{1 + i // 28:02d}-{1 + i % 28:02d}", [1, 0, 0, 0, 0, 0, 0] if i < 200 else [0, 1, 0, 0, 0, 0, 0])
            for i in range(336)]
    big = {"project": "big", "days": days, "commits": [],
           "clusters": [{"start": days[0]["d"], "end": days[-1]["d"], "commits": 336, "k": [200, 136, 0, 0, 0, 0, 0]}]}
    # 2b. same days, but the era's counts disagree: the era's counts win
    skew = dict(big, project="skew", clusters=[dict(big["clusters"][0], k=[168, 168, 0, 0, 0, 0, 0])])
    # 3. many eras of very different sizes, kind counts only
    eras = [{"start": f"2024-0{m}-01", "end": f"2024-0{m}-02", "commits": n, "k": [n // 2, n - n // 2, 0, 0, 0, 0, 0]}
            for m, n in zip(range(1, 8), [3, 500, 12, 1, 80, 40, 7])]
    many = {"project": "many", "days": [], "commits": [], "clusters": eras}
    # 4. an era with no kind data at all
    bare = {"project": "bare", "days": [], "commits": [], "clusters": [{"start": "2024-01-01", "end": "2024-01-01", "commits": 5}]}
    return [small, big, many, bare, skew]


def _check(d, layout):
    for c, e in zip(d.get("clusters", []), layout):
        span = e["f0"] - e["f1"]
        kc = c.get("k") if c.get("k") and any(c["k"]) else [0] * 6 + [1]
        tot = sum(kc)
        # P1: thickness share equals commit share, within 1%
        got = [0.0] * 7
        for r in e["runs"]:
            got[r["j"]] += (r["g0"] - r["g1"]) / span
        for j in range(7):
            assert abs(got[j] - kc[j] / tot) <= 0.01, (d["project"], KINDS[j], got[j], kc[j] / tot)
        # bands tile the era with no gaps
        assert abs(e["runs"][0]["g0"] - e["f0"]) < 1e-9 and abs(e["runs"][-1]["g1"] - e["f1"]) < 1e-9
        # P3: chunk thickness >= 3px unless chunks are single commits
        if e["chunks"] < e["n"]:
            assert span * RAD / e["chunks"] >= 3 - 1e-9, (d["project"], span * RAD / e["chunks"])


needs_node = pytest.mark.skipif(not shutil.which("node"), reason="node not installed")


@needs_node
def test_share_and_legibility_on_synthetic_digs():
    cases = _cases()
    for d, layout in zip(cases, _layout(cases)):
        _check(d, layout)


@needs_node
def test_small_era_keeps_exact_commit_order():
    small = _cases()[0]
    runs = _layout([small])[0][0]["runs"]
    # P2: rim to core = feat, fix, docs, other (exact order, one commit per chunk)
    assert [KINDS[r["j"]] for r in runs] == ["feat", "fix", "docs", "other"]
    assert [r["n"] for r in runs] == [2, 1, 1, 3]
    assert [r["per"] for r in runs] == [2, 1, 1, 3]  # striations count commits


@needs_node
def test_big_era_is_chronological_at_chunk_resolution():
    big = _cases()[1]
    runs = _layout([big])[0][0]["runs"]
    # P2: the older feat half is at the rim, the newer fix half nearer the core
    assert KINDS[runs[0]["j"]] == "feat" and KINDS[runs[-1]["j"]] == "fix"
    assert len(runs) <= 3  # one boundary chunk may hold both kinds
    feat = sum(r["n"] for r in runs if KINDS[r["j"]] == "feat")
    assert feat == 200


@needs_node
def test_real_digs_hold_the_same_rules():
    roots = [Path.home() / ".hermes-org/plugin-data/ag4te/projects", Path.home() / ".hermes/plugin-data/ag4te/projects"]
    digs = [p for r in roots if r.is_dir() for p in sorted(r.glob("*/dig.json"))]
    if not digs:
        pytest.skip("no real digs on this machine")
    cases = [json.loads(p.read_text()) for p in digs]
    for d, layout in zip(cases, _layout(cases)):
        _check(d, layout)
