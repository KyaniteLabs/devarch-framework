"""Regression pin: SWOT matrix counts used an undefined name for strengths."""

from archaeology.api import _parse_swot


def test_swot_matrix_counts_parse_every_quadrant(tmp_path):
    strategy = tmp_path / "deliverables" / "strategy"
    strategy.mkdir(parents=True)
    (strategy / "SWOT-ANALYSIS.md").write_text(
        "# SWOT\n"
        "Strengths: 3 found\nWeaknesses: 2 found\n"
        "Opportunities: 4 found\nThreats: 1 found\n"
        "## Strengths\n- Fast\n## Weaknesses\n- Thin docs\n",
        encoding="utf-8",
    )
    result = _parse_swot(tmp_path)
    assert result["strengths_count"] == 3
    assert result["weaknesses_count"] == 2
    assert result["opportunities_count"] == 4
    assert result["threats_count"] == 1
    assert result["strengths"] == ["Fast"]
