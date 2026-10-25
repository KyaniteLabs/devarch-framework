"""Regression pin: SWOT counts must work on the generator's real output.

The old parser built the strengths key from an undefined name and searched
only the title line, so real SWOT-ANALYSIS.md files never produced counts.
"""

from archaeology.api import _parse_swot
from scripts.data.generate_template_deliverables import strategy_swot_analysis


def _project():
    return {
        "name": "demo", "description": "", "lifespan": "1y", "total_commits": 200,
        "active_days": 20, "span_days": 365, "era_count": 4, "peak_day_commits": 30,
        "peak_day": "2026-01-01", "contributors": ["a"], "gaps": [], "analysis": {},
        "commit_types": {"feat": 60, "fix": 30, "docs": 0, "test": 10, "ci": 0, "refactor": 5},
    }


def test_swot_counts_match_generated_lists(tmp_path):
    strategy = tmp_path / "deliverables" / "strategy"
    strategy.mkdir(parents=True)
    (strategy / "SWOT-ANALYSIS.md").write_text(strategy_swot_analysis(_project()), encoding="utf-8")
    result = _parse_swot(tmp_path)
    for quadrant in ("strengths", "weaknesses", "opportunities", "threats"):
        assert result[f"{quadrant}_count"] == len(result[quadrant])
    assert result["strengths_count"] > 0
