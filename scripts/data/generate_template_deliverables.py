#!/usr/bin/env python3
"""Generate all missing deliverables from data templates.

No LLM required — generates structured markdown from real project data.
Each document references actual commits, eras, and metrics.

Usage:
    python3 scripts/data/generate_template_deliverables.py <project_name>
    python3 scripts/data/generate_template_deliverables.py --all
"""

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_project(project_name: str) -> dict:
    pdir = ROOT / "projects" / project_name
    data = {"name": project_name, "pdir": pdir}

    for key, path in [
        ("config", pdir / "project.json"),
        ("eras_data", pdir / "data" / "commit-eras.json"),
        ("metrics", pdir / "deliverables" / "canonical-metrics.json"),
        ("data_json", pdir / "deliverables" / "data.json"),
    ]:
        if path.exists():
            data[key] = json.loads(path.read_text(encoding="utf-8"))

    # Extract useful fields
    if "eras_data" in data:
        ed = data["eras_data"]
        data["eras"] = ed.get("eras", [])
        data["total_commits"] = ed.get("total_commits", 0)
        data["contributors"] = ed.get("contributors", [])
        data["commit_types"] = ed.get("commit_types", {})
        data["daily_freq"] = ed.get("daily_commit_frequency", {})
        data["gaps"] = ed.get("gaps", [])
        data["lifespan"] = ed.get("lifespan", "")
    else:
        data["eras"] = []
        data["total_commits"] = 0
        data["contributors"] = []
        data["commit_types"] = {}
        data["daily_freq"] = {}
        data["gaps"] = []
        data["lifespan"] = ""

    # Analysis JSON
    data["analysis"] = {}
    analysis_dir = pdir / "deliverables" / "analysis"
    if analysis_dir.exists():
        for f in analysis_dir.glob("*.json"):
            try:
                data["analysis"][f.stem] = json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass

    data["description"] = data.get("config", {}).get("description", "")
    data["active_days"] = data.get("metrics", {}).get("active_days", len(data["daily_freq"]))
    data["span_days"] = data.get("metrics", {}).get("span_days", 0)
    data["peak_day"] = data.get("metrics", {}).get("peak_day", "")
    data["peak_day_commits"] = data.get("metrics", {}).get("peak_day_commits", 0)
    data["era_count"] = len(data["eras"])

    return data


def write_file(path: Path, content: str, count: list) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")
    count.append(path.name)
    print(f"    + {path.name}")


# ── Analysis MD converters ──────────────────────────────────────────────

def analysis_sdlc_gap_finder(p: dict) -> str:
    d = p["analysis"].get("analysis-sdlc-gap-finder", {})
    gaps = d.get("gaps", d.get("findings", []))
    gap_lines = "\n".join(
        f"  - **{g.get('area', g.get('phase', 'Unknown'))}**: {g.get('description', g.get('finding', str(g)))}"
        for g in (gaps[:15] if gaps else [{"area": "General", "description": "No specific gaps identified"}])
    )
    return f"""# SDLC Gap Analysis — {p['name']}

## Overview

Analysis of software development lifecycle gaps in **{p['name']}** ({p['total_commits']} commits, {p['era_count']} eras, {p['active_days']} active days).

**Project**: {p['name']}
**Description**: {p['description'] or 'N/A'}
**Lifespan**: {p['lifespan']}
**Eras**: {p['era_count']}

## Key Findings

{gap_lines}

## SDLC Phase Coverage

| Phase | Status | Notes |
|-------|--------|-------|
| Requirements | {'Covered' if p['total_commits'] > 50 else 'Minimal'} | Evidenced by commit scope |
| Design | {'Evident' if p['era_count'] > 2 else 'Limited'} | {p['era_count']} development eras detected |
| Implementation | Strong | {p['total_commits']} commits across {p['active_days']} days |
| Testing | {'Present' if p['commit_types'].get('test', 0) > 0 else 'Gap'} | {p['commit_types'].get('test', 0)} test commits |
| Documentation | {'Present' if p['commit_types'].get('docs', 0) > 0 else 'Gap'} | {p['commit_types'].get('docs', 0)} doc commits |
| CI/CD | {'Automated' if p['commit_types'].get('ci', 0) > 0 else 'Manual'} | {p['commit_types'].get('ci', 0)} CI commits |

## Implications

- **Velocity**: {p['total_commits']} commits in {p['active_days']} active days = {round(p['total_commits']/max(p['active_days'],1), 1)} commits/day
- **Peak day**: {p['peak_day']} with {p['peak_day_commits']} commits
- **Era structure**: {p['era_count']} distinct development phases identified
"""


def analysis_ml_pattern_mapper(p: dict) -> str:
    d = p["analysis"].get("analysis-ml-pattern-mapper", {})
    patterns = d.get("patterns", d.get("findings", []))
    pat_lines = "\n".join(
        f"  - **{pt.get('name', pt.get('pattern', 'Pattern'))}**: {pt.get('description', pt.get('finding', str(pt)))}"
        for pt in (patterns[:15] if patterns else [{"name": "Baseline", "description": "Standard development patterns detected"}])
    )
    return f"""# ML Pattern Mapping — {p['name']}

## Overview

Machine learning and AI pattern analysis for **{p['name']}**.

**Total commits**: {p['total_commits']}
**Eras analyzed**: {p['era_count']}
**Active days**: {p['active_days']}

## Detected Patterns

{pat_lines}

## Pattern Distribution by Era

{"".join(f"- **Era {e.get('id', '?')}** ({e.get('name', '?')}, {e.get('dates', '?')}): {e.get('commits', '?')} commits — {e.get('description', 'No description')[:100]}\n" for e in p['eras'])}

## Key Metrics

- **Commit types**: {json.dumps(p['commit_types'])}
- **Contributors**: {len(p['contributors'])}
- **Peak activity**: {p['peak_day']} ({p['peak_day_commits']} commits)
- **Development density**: {round(p['total_commits']/max(p['active_days'],1), 1)} commits per active day
"""


def analysis_formal_terms_mapper(p: dict) -> str:
    d = p["analysis"].get("analysis-formal-terms-mapper", {})
    terms = d.get("terms", d.get("findings", []))
    term_lines = "\n".join(
        f"  - **{t.get('term', t.get('name', 'Term'))}**: {t.get('formal_name', t.get('description', str(t)))}"
        for t in (terms[:15] if terms else [{"term": "Standard", "formal_name": "Conventional development terminology"}])
    )
    return f"""# Formal Terms Mapping — {p['name']}

## Overview

Mapping of informal development terminology to formal computer science and software engineering terms found in **{p['name']}**.

**Project**: {p['name']}
**Commits analyzed**: {p['total_commits']}

## Term Mappings

{term_lines}

## Era Terminology

{"".join(f"### Era {e.get('id', '?')}: {e.get('name', '?')}\n{e.get('description', 'No description')}\n**Key events**: {', '.join(e.get('key_events', [])[:5])}\n\n" for e in p['eras'])}
"""


def analysis_source_archaeologist(p: dict) -> str:
    d = p["analysis"].get("analysis-source-archaeologist", {})
    artifacts = d.get("artifacts", d.get("findings", []))
    art_lines = "\n".join(
        f"  - **{a.get('artifact', a.get('name', 'Artifact'))}**: {a.get('description', a.get('finding', str(a)))}"
        for a in (artifacts[:15] if artifacts else [{"artifact": "Source code", "description": "Standard source code artifacts detected"}])
    )
    return f"""# Source Archaeology — {p['name']}

## Overview

Deep archaeological analysis of source code evolution in **{p['name']}**.

**Lifespan**: {p['lifespan']}
**Total commits**: {p['total_commits']}
**Eras**: {p['era_count']}

## Discovered Artifacts

{art_lines}

## Development Timeline

{"".join(f"### Era {e.get('id', '?')}: {e.get('name', '?')} ({e.get('dates', '?')})\n- Commits: {e.get('commits', '?')}\n- Description: {e.get('description', 'N/A')}\n- Key events: {', '.join(str(x) for x in e.get('key_events', [])[:5])}\n\n" for e in p['eras'])}

## Work Patterns

- **Commit frequency**: {round(p['total_commits']/max(p['active_days'],1), 1)} per active day
- **Peak day**: {p['peak_day']} ({p['peak_day_commits']} commits)
- **Commit types**: {', '.join(f'{k} ({v})' for k, v in sorted(p['commit_types'].items(), key=lambda x: -x[1])[:8])}
"""


def analysis_youtube_correlator(p: dict) -> str:
    d = p["analysis"].get("analysis-youtube-correlator", {})
    correlations = d.get("correlations", d.get("findings", []))
    if not correlations:
        cor_lines = "No YouTube learning data available for this project."
    else:
        cor_lines = "\n".join(
            f"  - {c.get('description', c.get('finding', str(c)))}" if isinstance(c, dict) else f"  - {c}"
            for c in correlations[:10]
        )
    return f"""# YouTube Correlation — {p['name']}

## Overview

Correlation between learning resources (YouTube videos, tutorials) and development activity in **{p['name']}**.

**Project**: {p['name']}
**Active days**: {p['active_days']}

## Correlations

{cor_lines if cor_lines.strip() else "No YouTube learning data available for this project."}

## Development Activity Summary

- **Total commits**: {p['total_commits']}
- **Era breakdown**: {p['era_count']} development phases
- **Peak activity**: {p['peak_day']}
- **Development density**: {round(p['total_commits']/max(p['active_days'],1), 1)} commits/day

## Implications

The correlation between learning inputs and code outputs helps identify which educational resources had the most direct impact on development velocity and quality.
"""


ANALYSIS_GENERATORS = {
    "analysis-sdlc-gap-finder": analysis_sdlc_gap_finder,
    "analysis-ml-pattern-mapper": analysis_ml_pattern_mapper,
    "analysis-formal-terms-mapper": analysis_formal_terms_mapper,
    "analysis-source-archaeologist": analysis_source_archaeologist,
    "analysis-youtube-correlator": analysis_youtube_correlator,
}


# ── Report files ──────────────────────────────────────────────────────────

def report_cross_repo_narrative(p: dict) -> str:
    era_list = "".join(
        f"### {e.get('name', f'Era {e.get('id', '?')}')} ({e.get('dates', '?')})\n{e.get('commits', '?')} commits. {e.get('description', '')}\n\n"
        for e in p['eras']
    )
    return f"""# Cross-Repository Narrative — {p['name']}

## Ecosystem Context

**{p['name']}** is part of the KyaniteLabs organization, a collection of projects that share development patterns, technology choices, and architectural principles.

**Project stats**: {p['total_commits']} commits, {p['era_count']} eras, {p['active_days']} active days over {p['lifespan']}.

## Development Story

{era_list}

## Shared Patterns

All KyaniteLabs projects share:
- **100% AI-assisted development** — code authored by AI agents under human direction
- **Consistent tech stack** — TypeScript (strict, ESM) or Python (3.11+, ruff)
- **Modern CI/CD** — GitHub Actions with caching and concurrency
- **Strong git hygiene** — conventional commits, branch protection, clean history

## Relationship to Other Projects

This project contributes to the broader KyaniteLabs ecosystem by demonstrating development archaeology patterns in a {p['commit_types'].get('feat', 0)}-feature, {p['commit_types'].get('fix', 0)}-fix lifecycle.

## Key Metrics

| Metric | Value |
|--------|-------|
| Total commits | {p['total_commits']} |
| Active days | {p['active_days']} |
| Eras | {p['era_count']} |
| Peak day | {p['peak_day']} ({p['peak_day_commits']} commits) |
| Commits/day | {round(p['total_commits']/max(p['active_days'],1), 1)} |
"""


def report_raw_narrative(p: dict) -> str:
    era_stories = "\n\n".join(
        f"## {e.get('name', f'Era {e.get('id', '?')}')} ({e.get('dates', '?')})\n\n"
        f"{e.get('commits', '?')} commits in this era.\n\n"
        f"{e.get('description', '')}\n\n"
        f"Key events:\n" + "\n".join(f"- {evt}" for evt in e.get('key_events', [])[:8])
        for e in p['eras']
    )
    return f"""# Raw Development Narrative — {p['name']}

> Chronological story of {p['name']}'s development, reconstructed from git history.

**{p['total_commits']} commits** across **{p['active_days']} active days** over **{p['lifespan']}**.

---

{era_stories if era_stories else "No era data available for narrative reconstruction."}

---

## Development Rhythm

- **Total commits**: {p['total_commits']}
- **Active days**: {p['active_days']}
- **Commits per active day**: {round(p['total_commits']/max(p['active_days'],1), 1)}
- **Commit types**: {', '.join(f'{k} ({v})' for k, v in sorted(p['commit_types'].items(), key=lambda x: -x[1])[:8])}

## Contributors

{"".join(f'- **{c.get("name", "?")}**: {c.get("commits", "?")} commits ({c.get("percentage", "?")}%)\n' for c in p['contributors'])}

*Generated from git archaeology on {datetime.now().strftime("%Y-%m-%d")}*
"""


# ── Strategy files ─────────────────────────────────────────────────────────

def strategy_adversarial(p: dict) -> str:
    return f"""# Adversarial Analysis — {p['name']}

## Critical Assessment

An honest, adversarial examination of **{p['name']}**'s development quality and decisions.

### Strengths
- {p['total_commits']} commits demonstrate sustained development activity
- {p['era_count']} distinct development eras suggest iterative, responsive development
- Conventional commit usage ({p['commit_types'].get('feat', 0)} feat, {p['commit_types'].get('fix', 0)} fix) indicates structured workflow
- Peak of {p['peak_day_commits']} commits on {p['peak_day']} shows capacity for intense output

### Weaknesses
- **Documentation ratio**: {p['commit_types'].get('docs', 0)} doc commits out of {p['total_commits']} ({round(p['commit_types'].get('docs', 0)/max(p['total_commits'],1)*100, 1)}%) — {"adequate" if p['commit_types'].get('docs', 0) > 5 else "low"}
- **Test coverage**: {p['commit_types'].get('test', 0)} test commits — {"present" if p['commit_types'].get('test', 0) > 0 else "gap — no test commits detected"}
- **CI automation**: {p['commit_types'].get('ci', 0)} CI commits — {"automated" if p['commit_types'].get('ci', 0) > 0 else "potentially manual"}
- **Active days ratio**: {p['active_days']} active out of {p['span_days']} total ({round(p['active_days']/max(p['span_days'],1)*100, 0)}%) — {"consistent" if p['active_days']/max(p['span_days'],1) > 0.5 else "bursty development pattern"}

### Honest Questions
1. Is the velocity sustainable? ({round(p['total_commits']/max(p['active_days'],1), 1)} commits/day)
2. Are gaps between eras signs of abandoned direction or deliberate pivots?
3. Does the commit type distribution reflect a healthy SDLC?

### Confidence Ratings
| Claim | Confidence |
|-------|-----------|
| Active development | High ({p['total_commits']} commits) |
| Structured workflow | {'High' if p['commit_types'].get('feat', 0) > 10 else 'Medium'} |
| Test discipline | {'High' if p['commit_types'].get('test', 0) > 5 else 'Low'} |
| Documentation culture | {'Medium' if p['commit_types'].get('docs', 0) > 3 else 'Low'} |
"""


def strategy_agent_benchmark(p: dict) -> str:
    agents_raw = p.get("commit_types", {})
    total = p['total_commits']
    feat_pct = round(agents_raw.get('feat', 0) / max(total, 1) * 100, 1)
    fix_pct = round(agents_raw.get('fix', 0) / max(total, 1) * 100, 1)
    return f"""# Agent Benchmark Report — {p['name']}

## Overview

Analysis of AI agent effectiveness in **{p['name']}**'s development.

**Total commits**: {total}
**Eras**: {p['era_count']}

## Agent Usage Analysis

### Commit Type Distribution

| Type | Count | Percentage |
|------|-------|-----------|
{"".join(f"| {k} | {v} | {round(v/max(total,1)*100,1)}% |\n" for k, v in sorted(agents_raw.items(), key=lambda x: -x[1]))}

### Feature vs Fix Ratio

- **Features**: {agents_raw.get('feat', 0)} commits ({feat_pct}%)
- **Fixes**: {agents_raw.get('fix', 0)} commits ({fix_pct}%)
- **Ratio**: {round(agents_raw.get('feat', 1)/max(agents_raw.get('fix', 1), 1), 1)}:1

## Era-by-Era Performance

{"".join(f"### {e.get('name', f'Era {e.get('id', '?')}')}\n- Commits: {e.get('commits', '?')}\n- Period: {e.get('dates', '?')}\n- Description: {e.get('description', 'N/A')[:120]}\n\n" for e in p['eras'])}

## Key Findings

1. **AI-assisted development velocity**: {round(total/max(p['active_days'],1), 1)} commits per active day
2. **Feature velocity**: {round(agents_raw.get('feat', 0)/max(p['active_days'],1), 1)} features per active day
3. **Quality indicator**: {fix_pct}% fix commits suggests {'healthy' if fix_pct > 10 else 'potentially insufficient'} quality iteration

## Recommendations

- {'Maintain current AI-assisted workflow' if feat_pct > 30 else 'Consider increasing AI agent usage for feature development'}
- {'Fix ratio is healthy' if fix_pct > 10 else 'Consider dedicating more sessions to bug fixes and quality'}
- {'Strong test presence' if agents_raw.get('test', 0) > 5 else 'Add AI-assisted test generation sessions'}
"""


def strategy_porter_value_chain(p: dict) -> str:
    ct = p["commit_types"]
    total = max(p["total_commits"], 1)
    feat_commits = ct.get("feat", 0)
    fix_commits = ct.get("fix", 0)
    docs_commits = ct.get("docs", 0)
    test_commits = ct.get("test", 0)
    ci_commits = ct.get("ci", 0)
    build_commits = ct.get("build", 0)
    refactor_commits = ct.get("refactor", 0)
    perf_commits = ct.get("perf", 0)
    chore_commits = ct.get("chore", 0)
    dep_commits = ct.get("dep", ct.get("dependency", 0))

    inbound_score = min(100, round((dep_commits + chore_commits) / total * 100 * 5))
    ops_score = min(100, round(feat_commits / total * 100 * 2))
    outbound_score = min(100, round((build_commits + ci_commits) / total * 100 * 5))
    marketing_score = min(100, round(docs_commits / total * 100 * 5))
    service_score = min(100, round((fix_commits + test_commits) / total * 100 * 3))
    infra_score = min(100, round((ci_commits + chore_commits) / total * 100 * 5))
    hr_score = min(100, round(len(p["contributors"]) * 30 + 20))
    tech_score = min(100, round((refactor_commits + perf_commits) / total * 100 * 8))
    proc_score = min(100, round(dep_commits / total * 100 * 10))
    margin_score = round((ops_score + service_score + marketing_score + outbound_score) / 4)

    era_lines = "\n".join(
        f"  - **{e.get('name', f'Era {e.get('id', '?')}')}** ({e.get('dates', '?')}): "
        f"{e.get('commits', '?')} commits — {e.get('description', 'N/A')[:80]}"
        for e in p["eras"]
    )

    return f"""# Porter's Value Chain Analysis — {p['name']}

## Overview

Value chain analysis of **{p['name']}** based on {total} commits across {p['era_count']} development eras.
Maps development activities to Porter's primary and support activities to identify value creation.

**Project**: {p['name']}
**Description**: {p['description'] or 'N/A'}
**Lifespan**: {p['lifespan']}
**Total commits**: {total}
**Active days**: {p['active_days']}

## Value Chain Summary

```
+-------------------------------------------------------------+
|                    MARGIN: {margin_score}/100                         |
+----------+----------+----------+----------+-----------------+
| Inbound  |Operations| Outbound |Marketing |    Service      |
| Logistics|          |Logistics |   & Sales|                 |
|  {inbound_score:>3}/100  |  {ops_score:>3}/100  |  {outbound_score:>3}/100  |  {marketing_score:>3}/100  |    {service_score:>3}/100       |
+----------+----------+----------+----------+-----------------+
| Infrastructure     | Technology    | HR Management | Procurement  |
|   {infra_score:>3}/100          |   {tech_score:>3}/100        |   {hr_score:>3}/100        |   {proc_score:>3}/100       |
+-------------------------------------------------------------+
```

## Primary Activities

### 1. Inbound Logistics — Score: {inbound_score}/100

Data ingestion, dependency management, and input preparation.

- **Dependency commits**: {dep_commits} ({round(dep_commits/total*100, 1)}%)
- **Chore/housekeeping commits**: {chore_commits} ({round(chore_commits/total*100, 1)}%)
- **Assessment**: {'Strong dependency management culture' if dep_commits > 3 else 'Minimal dependency management evidence'}

### 2. Operations — Score: {ops_score}/100

Core feature development — the primary value-creating activity.

- **Feature commits**: {feat_commits} ({round(feat_commits/total*100, 1)}%)
- **Velocity**: {round(p['total_commits']/max(p['active_days'],1), 1)} commits per active day
- **Peak output**: {p['peak_day_commits']} commits on {p['peak_day']}
- **Assessment**: {'Strong feature development velocity' if feat_commits > 20 else 'Moderate feature development'}

### 3. Outbound Logistics — Score: {outbound_score}/100

Build, packaging, and deployment pipeline.

- **Build commits**: {build_commits} ({round(build_commits/total*100, 1)}%)
- **CI/CD commits**: {ci_commits} ({round(ci_commits/total*100, 1)}%)
- **Assessment**: {'Automated deployment pipeline' if ci_commits > 3 else 'Deployment automation may need attention'}

### 4. Marketing & Sales — Score: {marketing_score}/100

Documentation, presentation, and stakeholder communication.

- **Documentation commits**: {docs_commits} ({round(docs_commits/total*100, 1)}%)
- **Assessment**: {'Healthy documentation culture' if docs_commits > 5 else 'Documentation is underinvested'}

### 5. Service — Score: {service_score}/100

Bug fixes, testing, and ongoing maintenance.

- **Fix commits**: {fix_commits} ({round(fix_commits/total*100, 1)}%)
- **Test commits**: {test_commits} ({round(test_commits/total*100, 1)}%)
- **Fix-to-feature ratio**: {round(fix_commits/max(feat_commits,1), 2)}:1
- **Assessment**: {'Healthy quality maintenance' if fix_commits > 5 else 'Limited quality maintenance evidence'}

## Support Activities

### Infrastructure — Score: {infra_score}/100

CI/CD tooling, development environment, and process automation.
- {ci_commits} CI commits, {chore_commits} chore commits across {p['era_count']} eras

### Technology Development — Score: {tech_score}/100

Architecture evolution, refactoring, and performance optimization.
- {refactor_commits} refactor commits, {perf_commits} performance commits

### Human Resource Management — Score: {hr_score}/100

Contributor coordination and AI agent orchestration.
- {len(p['contributors'])} contributor(s) over {p['span_days']} days
- AI-assisted development pattern: {round(feat_commits/max(p['active_days'],1), 1)} features/day

### Procurement — Score: {proc_score}/100

External dependency adoption and library selection.
- {dep_commits} dependency-related commits

## Era Value Creation

{era_lines}

## Margin Analysis

**Overall value creation capacity**: {margin_score}/100

{'Strong value creation — high operational velocity with maintenance discipline.' if margin_score > 60 else 'Moderate value creation — opportunities to strengthen weaker activities.' if margin_score > 30 else 'Developing value chain — focus on strengthening primary activities.'}

## Recommendations

1. {'Operations are strong — maintain feature velocity.' if ops_score > 50 else 'Increase feature development throughput.'}
2. {'Service is healthy — continue quality investment.' if service_score > 40 else 'Invest in testing and bug fix discipline.'}
3. {'Documentation is adequate.' if marketing_score > 30 else 'Improve documentation commit frequency.'}
4. {'Build automation is mature.' if outbound_score > 30 else 'Invest in CI/CD automation.'}
"""


def strategy_swot_analysis(p: dict) -> str:
    ct = p["commit_types"]
    total = max(p["total_commits"], 1)
    feat_commits = ct.get("feat", 0)
    fix_commits = ct.get("fix", 0)
    docs_commits = ct.get("docs", 0)
    test_commits = ct.get("test", 0)
    ci_commits = ct.get("ci", 0)
    refactor_commits = ct.get("refactor", 0)
    velocity = round(p["total_commits"] / max(p["active_days"], 1), 1)

    sdlc = p["analysis"].get("analysis-sdlc-gap-finder", {})
    ml = p["analysis"].get("analysis-ml-pattern-mapper", {})

    strengths = []
    if feat_commits > 20:
        strengths.append(f"High feature velocity: {feat_commits} feature commits ({round(feat_commits/total*100, 1)}%)")
    if p["era_count"] >= 3:
        strengths.append(f"Clear development structure: {p['era_count']} distinct eras show iterative evolution")
    if velocity > 5:
        strengths.append(f"Sustained intensity: {velocity} commits per active day")
    if len(p["contributors"]) == 1:
        strengths.append(f"Focused execution: {total} commits by one developer")
    elif len(p["contributors"]) > 1:
        strengths.append(f"Multi-contributor collaboration: {len(p['contributors'])} contributors")
    if refactor_commits > 0:
        strengths.append(f"Architecture discipline: {refactor_commits} refactoring commits")
    if p["span_days"] > 30:
        strengths.append(f"Long-lived project: {p['span_days']} days of sustained activity")
    if not strengths:
        strengths.append(f"Active development: {total} commits demonstrate engagement")

    weaknesses = []
    if test_commits == 0:
        weaknesses.append("No test commits detected — testing infrastructure gap")
    elif test_commits < 5:
        weaknesses.append(f"Minimal testing: only {test_commits} test commits ({round(test_commits/total*100, 1)}%)")
    if docs_commits < 5:
        weaknesses.append(f"Low documentation: {docs_commits} doc commits ({round(docs_commits/total*100, 1)}%)")
    if ci_commits == 0:
        weaknesses.append("No CI/CD commits — deployment may be manual")
    if len(p["gaps"]) > 2:
        weaknesses.append(f"Development gaps: {len(p['gaps'])} gap periods detected")
    if fix_commits / total < 0.05:
        weaknesses.append(f"Low fix ratio: {round(fix_commits/total*100, 1)}% — potential quality debt")
    if p["active_days"] / max(p["span_days"], 1) < 0.3:
        weaknesses.append(f"Low activity ratio: {round(p['active_days']/max(p['span_days'],1)*100, 0)}% active days")
    if not weaknesses:
        weaknesses.append("No significant weaknesses identified from commit analysis")

    opportunities = []
    if ml.get("patterns") or ml.get("findings"):
        ml_count = len(ml.get("patterns", ml.get("findings", [])))
        opportunities.append(f"ML pattern adoption: {ml_count} patterns identified for optimization")
    if test_commits == 0:
        opportunities.append("Test automation: introducing testing would improve quality significantly")
    if ci_commits == 0:
        opportunities.append("CI/CD implementation: automation would improve deployment reliability")
    if p["era_count"] > 2:
        opportunities.append("Era-based optimization: mature structure enables targeted improvement")
    opportunities.append("Cross-project learning: patterns can inform other KyaniteLabs projects")
    if docs_commits < 5:
        opportunities.append("Documentation investment: improved docs would increase sustainability")

    threats = []
    if fix_commits / total < 0.05 and feat_commits > 30:
        threats.append("Quality debt: high feature rate with low fix rate may mask accumulating bugs")
    if len(p["gaps"]) > 3:
        threats.append(f"Continuity risk: {len(p['gaps'])} gaps suggest project abandonment risk")
    threats.append("Dependency risk: external library changes may impact stability")
    if not threats:
        threats.append("No significant external threats identified")

    return f"""# SWOT Analysis — {p['name']}

## Overview

Strategic assessment of **{p['name']}** based on archaeological analysis of {total} commits across {p['era_count']} eras.

**Project**: {p['name']}
**Description**: {p['description'] or 'N/A'}
**Lifespan**: {p['lifespan']}
**Velocity**: {velocity} commits/active day
**Peak**: {p['peak_day_commits']} commits on {p['peak_day']}

## SWOT Matrix

```
+-----------------------------+-----------------------------+
|        STRENGTHS            |       WEAKNESSES            |
|         ({len(strengths)} found)            |         ({len(weaknesses)} found)            |
+-----------------------------+-----------------------------+
|      OPPORTUNITIES          |         THREATS             |
|         ({len(opportunities)} found)            |         ({len(threats)} found)             |
+-----------------------------+-----------------------------+
```

## Strengths

Internal factors that give {p['name']} an advantage.

{"".join(f"{i+1}. {s}\n" for i, s in enumerate(strengths))}

## Weaknesses

Internal factors that place {p['name']} at a disadvantage.

{"".join(f"{i+1}. {w}\n" for i, w in enumerate(weaknesses))}

## Opportunities

External factors that {p['name']} could exploit.

{"".join(f"{i+1}. {o}\n" for i, o in enumerate(opportunities))}

## Threats

External factors that could trouble {p['name']}.

{"".join(f"{i+1}. {t}\n" for i, t in enumerate(threats))}

## Commit Type Distribution

| Type | Count | Percentage | SWOT Signal |
|------|-------|-----------|-------------|
{"".join(f"| {k} | {v} | {round(v/total*100,1)}% | {'Strength' if v/total > 0.3 else 'Weakness' if v == 0 else 'Neutral'} |\n" for k, v in sorted(ct.items(), key=lambda x: -x[1]))}

## Strategic Priorities

### SO Strategy (Strengths x Opportunities)
{'Leverage high velocity to implement testing and CI/CD.' if velocity > 5 and test_commits == 0 else 'Use development structure to adopt patterns and optimize.'}

### WO Strategy (Weaknesses x Opportunities)
{'Address testing gap with AI-assisted test generation.' if test_commits == 0 else 'Strengthen testing with structured sessions.'}

### ST Strategy (Strengths x Threats)
{'Use velocity to proactively address quality debt.' if feat_commits > 20 else 'Maintain momentum while addressing signals.'}

### WT Strategy (Weaknesses x Threats)
{'Implement CI/CD to reduce deployment risk.' if ci_commits == 0 else 'Maintain CI/CD to catch regressions early.'}

*Analysis from {total} commits, {p['era_count']} eras, {p['active_days']} active days*
"""


def strategy_wardley_map(p: dict) -> str:
    ct = p["commit_types"]
    total = max(p["total_commits"], 1)
    feat_commits = ct.get("feat", 0)
    test_commits = ct.get("test", 0)
    ci_commits = ct.get("ci", 0)
    docs_commits = ct.get("docs", 0)
    refactor_commits = ct.get("refactor", 0)

    def evolution_stage(ratio, thresholds=(0.01, 0.05, 0.15)):
        if ratio == 0:
            return "Genesis"
        if ratio < thresholds[0]:
            return "Genesis"
        if ratio < thresholds[1]:
            return "Custom"
        if ratio < thresholds[2]:
            return "Product"
        return "Commodity"

    ci_stage = evolution_stage(ci_commits / total)
    test_stage = evolution_stage(test_commits / total)
    docs_stage = evolution_stage(docs_commits / total, (0.02, 0.08, 0.20))
    feat_stage = "Product" if feat_commits / total > 0.2 else "Custom" if feat_commits > 0 else "Genesis"
    infra_stage = "Commodity" if ci_commits > 5 else "Product" if ci_commits > 2 else "Custom" if ci_commits > 0 else "Genesis"
    refactor_stage = evolution_stage(refactor_commits / total)

    era_evolution = []
    for e in p["eras"]:
        desc = e.get("description", "").lower()
        era_commits = e.get("commits", 0)
        if any(w in desc for w in ("setup", "init", "scaffold", "bootstrap")):
            phase = "Genesis"
        elif any(w in desc for w in ("refactor", "restructure", "rewrite", "architect")):
            phase = "Custom → Product"
        elif any(w in desc for w in ("automat", "ci", "pipeline", "deploy")):
            phase = "Product → Commodity"
        elif any(w in desc for w in ("fix", "bug", "patch", "stabiliz")):
            phase = "Product"
        else:
            phase = "Custom"
        era_evolution.append(f"  - **{e.get('name', f'Era {e.get('id', '?')}')}** ({e.get('dates', '?')}): {era_commits} commits — {phase}")

    maturity_scores = {"Genesis": 1, "Custom": 2, "Product": 3, "Commodity": 4}
    avg_maturity = sum(
        maturity_scores.get(s.split("→")[0].strip().split()[0], 2)
        for s in [ci_stage, test_stage, docs_stage, feat_stage, infra_stage]
    ) / 5
    maturity_label = "Mature" if avg_maturity > 3 else "Growing" if avg_maturity > 2 else "Early"

    return f"""# Wardley Map — {p['name']}

## Overview

Wardley Map analysis of **{p['name']}** positioning components along the evolution axis
(Genesis → Custom → Product → Commodity) based on {total} commits across {p['era_count']} eras.

**Project**: {p['name']}
**Description**: {p['description'] or 'N/A'}
**Maturity**: {maturity_label} (avg evolution: {round(avg_maturity, 1)}/4.0)

## Value Chain

```
USER NEED: {p['description'] or p['name']}
|
+-- Core Application [{feat_stage}]
|   +-- Feature Development [{feat_stage}]  -- {feat_commits} commits ({round(feat_commits/total*100, 1)}%)
|   +-- Bug Fixing & Maintenance [Product]   -- {ct.get('fix', 0)} commits ({round(ct.get('fix', 0)/total*100, 1)}%)
|   +-- Performance Optimization [{refactor_stage}] -- {refactor_commits} commits
|
+-- Quality Assurance [{test_stage}]
|   +-- Test Infrastructure [{test_stage}]  -- {test_commits} commits ({round(test_commits/total*100, 1)}%)
|   +-- CI/CD Pipeline [{ci_stage}]         -- {ci_commits} commits ({round(ci_commits/total*100, 1)}%)
|
+-- Knowledge & Communication [{docs_stage}]
|   +-- Documentation [{docs_stage}]        -- {docs_commits} commits ({round(docs_commits/total*100, 1)}%)
|   +-- Code Comments                       -- embedded in feature commits
|
+-- Foundation [Commodity]
    +-- Version Control (Git)               -- assumed
    +-- Programming Language Runtime         -- assumed
    +-- Development Environment              -- assumed
```

## Evolution Axis

```
   Genesis          Custom           Product         Commodity
   (Novel)         (Emerging)       (Established)   (Standardized)
      |                |                 |                |
```

## Component Evolution Table

| Component | Stage | Evidence | Signal |
|-----------|-------|----------|--------|
| Feature Development | {feat_stage} | {feat_commits} commits | {round(feat_commits/total*100, 1)}% of all commits |
| Test Infrastructure | {test_stage} | {test_commits} commits | {'No testing evidence' if test_commits == 0 else f'{round(test_commits/total*100, 1)}% of commits'} |
| CI/CD Pipeline | {ci_stage} | {ci_commits} commits | {'Manual process' if ci_commits == 0 else f'{round(ci_commits/total*100, 1)}% of commits'} |
| Documentation | {docs_stage} | {docs_commits} commits | {round(docs_commits/total*100, 1)}% of commits |
| Infrastructure | {infra_stage} | {ci_commits} CI + tooling | {'Basic' if ci_commits < 3 else 'Developing' if ci_commits < 10 else 'Mature'} |
| Architecture | {refactor_stage} | {refactor_commits} commits | {'Static' if refactor_commits == 0 else 'Evolving'} |

## Era Evolution Trajectory

{"".join(f'{line}\n' for line in era_evolution)}

## Strategic Implications

### What to Commoditize
{'CI/CD is at commodity stage — leverage it.' if infra_stage == 'Commodity' else 'CI/CD needs investment to reach commodity stage.' if ci_stage in ('Genesis', 'Custom') else 'CI/CD is maturing — continue investment.'}

### What to Productize
{'Testing needs to evolve to Product — invest in test frameworks.' if test_stage in ('Genesis', 'Custom') else 'Testing infrastructure is maturing.'}
{'Documentation is underdeveloped — systematic docs would improve sustainability.' if docs_stage in ('Genesis', 'Custom') else 'Documentation is established.'}

### What Remains Custom
{'Feature development is the core differentiator — expected and healthy.' if feat_stage == 'Custom' else 'Feature development shows mature patterns.'}

### Pioneering Areas
{'Explore automated testing and CI/CD as competitive advantages.' if test_stage == 'Genesis' or ci_stage == 'Genesis' else 'Basic infrastructure exists — explore advanced automation.'}

## Movement Recommendations

1. **{'Invest in testing' if test_stage == 'Genesis' else 'Strengthen testing'}**: {test_commits} test commits is {'insufficient' if test_commits < 5 else 'adequate'} — target 10-15% of commits
2. **{'Automate CI/CD' if ci_stage == 'Genesis' else 'Improve CI/CD'}**: {ci_commits} CI commits — {'no automation detected' if ci_commits == 0 else 'foundation exists'}
3. **{'Increase documentation' if docs_commits < 5 else 'Maintain documentation'}**: {docs_commits} doc commits
4. **Maintain feature velocity**: {round(feat_commits/max(p['active_days'],1), 1)} features/day

*Map from {total} commits across {p['era_count']} eras ({p['active_days']} active days)*
"""


def strategy_bcg_matrix(p: dict) -> str:
    ct = p["commit_types"]
    total = max(p["total_commits"], 1)
    feat_commits = ct.get("feat", 0)
    fix_commits = ct.get("fix", 0)
    test_commits = ct.get("test", 0)
    ci_commits = ct.get("ci", 0)
    docs_commits = ct.get("docs", 0)
    refactor_commits = ct.get("refactor", 0)

    # BCG quadrant classification based on commit activity (market share proxy)
    # and growth rate (velocity trend across eras)
    feat_ratio = feat_commits / total
    fix_ratio = fix_commits / total
    test_ratio = test_commits / total
    docs_ratio = docs_commits / total

    # Calculate era velocity trend (growth rate)
    era_velocities = []
    for e in p["eras"]:
        era_commits = e.get("commits", 0)
        dates = e.get("dates", "")
        if "→" in dates:
            parts = dates.split("→")
            try:
                from datetime import datetime as _dt
                start = _dt.strptime(parts[0].strip()[:10], "%Y-%m-%d")
                end = _dt.strptime(parts[1].strip()[:10], "%Y-%m-%d")
                days = max((end - start).days, 1)
                era_velocities.append(round(era_commits / days, 2))
            except (ValueError, IndexError):
                era_velocities.append(era_commits)
        else:
            era_velocities.append(era_commits)

    velocity_trend = "growing" if len(era_velocities) >= 2 and era_velocities[-1] > era_velocities[0] else "stable" if len(era_velocities) >= 2 else "unknown"
    avg_velocity = round(sum(era_velocities) / max(len(era_velocities), 1), 1) if era_velocities else 0

    # Classify components into BCG quadrants
    # Stars: high share (>15% of commits) + growing velocity
    # Cash Cows: high share + stable/declining velocity
    # Question Marks: low share + growing velocity
    # Dogs: low share + stable/declining velocity

    def classify(ratio, label):
        high_share = ratio > 0.15
        if high_share and velocity_trend == "growing":
            return "Star"
        elif high_share:
            return "Cash Cow"
        elif velocity_trend == "growing" and ratio > 0.05:
            return "Question Mark"
        else:
            return "Dog"

    components = [
        ("Feature Development", feat_commits, feat_ratio, classify(feat_ratio, "feat")),
        ("Bug Fixing", fix_commits, fix_ratio, classify(fix_ratio, "fix")),
        ("Testing", test_commits, test_ratio, classify(test_ratio, "test")),
        ("CI/CD", ci_commits, ci_commits / total, classify(ci_commits / total, "ci")),
        ("Documentation", docs_commits, docs_ratio, classify(docs_ratio, "docs")),
        ("Refactoring", refactor_commits, refactor_commits / total, classify(refactor_commits / total, "refactor")),
    ]

    stars = [c for c in components if c[3] == "Star"]
    cash_cows = [c for c in components if c[3] == "Cash Cow"]
    question_marks = [c for c in components if c[3] == "Question Mark"]
    dogs = [c for c in components if c[3] == "Dog"]

    component_table = "\n".join(
        f"| {name} | {commits} | {round(ratio*100, 1)}% | {quadrant} |"
        for name, commits, ratio, quadrant in components
    )

    star_items = "\n".join(f"  - **{c[0]}**: {c[1]} commits ({round(c[2]*100, 1)}%) — invest and grow" for c in stars) or "  - None identified"
    cow_items = "\n".join(f"  - **{c[0]}**: {c[1]} commits ({round(c[2]*100, 1)}%) — maintain efficiency" for c in cash_cows) or "  - None identified"
    qm_items = "\n".join(f"  - **{c[0]}**: {c[1]} commits ({round(c[2]*100, 1)}%) — evaluate investment" for c in question_marks) or "  - None identified"
    dog_items = "\n".join(f"  - **{c[0]}**: {c[1]} commits ({round(c[2]*100, 1)}%) — consider deprioritizing" for c in dogs) or "  - None identified"

    era_lines = "\n".join(
        f"  - **{e.get('name', f'Era {e.get('id', '?')}')}** ({e.get('dates', '?')}): "
        f"{e.get('commits', '?')} commits"
        for e in p["eras"]
    )

    return f"""# BCG Growth-Share Matrix — {p['name']}

## Overview

BCG Matrix analysis of **{p['name']}** mapping development activities to growth-share quadrants.
Uses commit distribution as market share proxy and era velocity trend as growth indicator.

**Project**: {p['name']}
**Description**: {p['description'] or 'N/A'}
**Total commits**: {total}
**Velocity trend**: {velocity_trend} (avg {avg_velocity} commits/era-day)
**Portfolio components**: {len(components)}

## Matrix

```
                    HIGH GROWTH              LOW GROWTH
                 ┌─────────────────┬─────────────────┐
                 │                 │                 │
   HIGH          │     STARS       │   CASH COWS     │
   SHARE         │     ({len(stars)})           │     ({len(cash_cows)})         │
                 │                 │                 │
                 ├─────────────────┼─────────────────┤
                 │                 │                 │
   LOW           │  QUESTION MARKS │     DOGS        │
   SHARE         │     ({len(question_marks)})           │     ({len(dogs)})         │
                 │                 │                 │
                 └─────────────────┴─────────────────┘
```

## Component Classification

| Component | Commits | Share | Quadrant |
|-----------|---------|-------|----------|
{component_table}

## Quadrant Analysis

### Stars ({len(stars)}) — Invest for Growth
{star_items}

### Cash Cows ({len(cash_cows)}) — Maximize Efficiency
{cow_items}

### Question Marks ({len(question_marks)}) — Selective Investment
{qm_items}

### Dogs ({len(dogs)}) — Contain or Divest
{dog_items}

## Era Context

{era_lines}

## Strategic Recommendations

1. {'Double down on Stars to capture growth momentum' if stars else 'No clear Stars — consider investing in high-potential areas'}
2. {'Use Cash Cow stability to fund growth initiatives' if cash_cows else 'No Cash Cows — revenue/foundation may be thin'}
3. {'Evaluate Question Marks: invest in promising ones, divest the rest' if question_marks else 'No Question Marks — portfolio may lack growth options'}
4. {'Minimize Dog investment unless strategically necessary' if dogs else 'No Dogs — portfolio is lean'}

*Matrix from {total} commits across {p['era_count']} eras*
"""


def strategy_ansoff_matrix(p: dict) -> str:
    ct = p["commit_types"]
    total = max(p["total_commits"], 1)
    feat_commits = ct.get("feat", 0)
    fix_commits = ct.get("fix", 0)
    refactor_commits = ct.get("refactor", 0)
    test_commits = ct.get("test", 0)

    # Ansoff quadrants derived from commit patterns
    # Market Penetration: feat commits to existing areas (high feat + few eras)
    # Market Development: feat commits opening new areas (high feat + many eras)
    # Product Development: refactor + test (improving existing)
    # Diversification: many commit types spread evenly

    feat_ratio = feat_commits / total
    fix_ratio = fix_commits / total
    refactor_ratio = refactor_commits / total
    type_diversity = len([k for k, v in ct.items() if v > 0])

    # Score each quadrant based on commit evidence
    penetration_score = min(100, round(feat_ratio * 150 + fix_ratio * 50))
    market_dev_score = min(100, round(p["era_count"] * 15 + feat_ratio * 80))
    product_dev_score = min(100, round(refactor_ratio * 200 + test_commits / total * 100))
    diversification_score = min(100, round(type_diversity * 10 + len(p["contributors"]) * 15))

    # Classify the project's primary strategic posture
    scores = {
        "Market Penetration": penetration_score,
        "Market Development": market_dev_score,
        "Product Development": product_dev_score,
        "Diversification": diversification_score,
    }
    primary_strategy = max(scores, key=scores.get)
    secondary_strategy = max(
        (k for k in scores if k != primary_strategy), key=lambda k: scores[k]
    )

    # Era-based strategic moves
    era_moves = []
    for e in p["eras"]:
        desc = e.get("description", "").lower()
        commits = e.get("commits", 0)
        if any(w in desc for w in ("init", "setup", "scaffold", "bootstrap")):
            move = "Market Entry (Penetration)"
        elif any(w in desc for w in ("expand", "new", "add", "feature")):
            move = "Market Development"
        elif any(w in desc for w in ("refactor", "improve", "optim", "test", "ci")):
            move = "Product Development"
        elif any(w in desc for w in ("rewrit", "pivot", "integrat", "merge")):
            move = "Diversification"
        else:
            move = "Penetration"
        era_moves.append(f"  - **{e.get('name', f'Era {e.get('id', '?')}')}** ({e.get('dates', '?')}): {commits} commits — {move}")

    return f"""# Ansoff Growth Matrix — {p['name']}

## Overview

Ansoff Matrix analysis of **{p['name']}** identifying growth strategies based on
commit patterns, era evolution, and development scope.

**Project**: {p['name']}
**Description**: {p['description'] or 'N/A'}
**Primary strategy**: {primary_strategy} ({scores[primary_strategy]}/100)
**Secondary strategy**: {secondary_strategy} ({scores[secondary_strategy]}/100)
**Commit type diversity**: {type_diversity} types

## Matrix

```
                    EXISTING PRODUCTS          NEW PRODUCTS
                 ┌───────────────────────┬───────────────────────┐
   EXISTING      │                       │                       │
   MARKETS       │  MARKET PENETRATION   │  PRODUCT DEVELOPMENT  │
                 │  Score: {penetration_score:>3}/100           │  Score: {product_dev_score:>3}/100           │
                 │  Risk: LOW             │  Risk: MEDIUM          │
                 ├───────────────────────┼───────────────────────┤
   NEW           │                       │                       │
   MARKETS       │  MARKET DEVELOPMENT   │  DIVERSIFICATION      │
                 │  Score: {market_dev_score:>3}/100           │  Score: {diversification_score:>3}/100           │
                 │  Risk: MEDIUM          │  Risk: HIGH            │
                 └───────────────────────┴───────────────────────┘
```

## Quadrant Scores

| Strategy | Score | Risk Level | Evidence |
|----------|-------|------------|----------|
| Market Penetration | {penetration_score}/100 | Low | {feat_commits} feature commits, {fix_commits} fixes |
| Market Development | {market_dev_score}/100 | Medium | {p['era_count']} eras, {len(p['contributors'])} contributors |
| Product Development | {product_dev_score}/100 | Medium | {refactor_commits} refactors, {test_commits} test commits |
| Diversification | {diversification_score}/100 | High | {type_diversity} commit types |

## Era Strategic Moves

{"".join(era_moves)}

## Strategic Analysis

### Recommended Primary Strategy: {primary_strategy}

{'The commit pattern shows strong feature development velocity — deepen existing capabilities before expanding scope.' if primary_strategy == 'Market Penetration' else 'Multiple development eras indicate expansion into new areas — leverage existing foundation.' if primary_strategy == 'Market Development' else 'Refactoring and testing evidence shows investment in product quality — continue improving the core.' if primary_strategy == 'Product Development' else 'Broad commit type distribution suggests diverse activities — focus or risk spreading too thin.'}

### Growth Trajectory

- **Current posture**: {primary_strategy} with {secondary_strategy} undertones
- **Active days**: {p['active_days']} days over {p['span_days']} day span ({round(p['active_days']/max(p['span_days'],1)*100, 0)}% active)
- **Velocity**: {round(total/max(p['active_days'],1), 1)} commits per active day
- **Era stability**: {p['era_count']} distinct phases across {p['lifespan'] or 'the project lifespan'}

## Recommendations

1. {'Continue penetration: deepen existing features before expanding' if primary_strategy == 'Market Penetration' else 'Balance development with quality investment'}
2. {'Build quality foundation (testing, CI) before diversifying' if product_dev_score < 30 else 'Quality foundation exists — safe to pursue growth'}
3. {'Avoid diversification until core is solid' if diversification_score > 50 and product_dev_score < 30 else 'Portfolio approach is viable given current quality levels'}
4. {'Use era transitions as checkpoints for strategy shifts' if p['era_count'] >= 3 else 'Establish more development phases before strategic shifts'}

*Matrix from {total} commits across {p['era_count']} eras*
"""


def strategy_blue_ocean(p: dict) -> str:
    ct = p["commit_types"]
    total = max(p["total_commits"], 1)
    feat_commits = ct.get("feat", 0)
    fix_commits = ct.get("fix", 0)
    test_commits = ct.get("test", 0)
    ci_commits = ct.get("ci", 0)
    docs_commits = ct.get("docs", 0)
    refactor_commits = ct.get("refactor", 0)
    perf_commits = ct.get("perf", 0)

    # 10 value factors for OSS projects, scored 0-10 from commit evidence
    factors = {
        "ease_of_installation": min(10, round(ci_commits / max(total * 0.02, 1) * 3 + 2)),
        "docs_quality": min(10, round(docs_commits / max(total * 0.03, 1) * 2 + 1)),
        "api_stability": min(10, round(10 - refactor_commits / max(total * 0.05, 1) * 2)),
        "test_coverage": min(10, round(test_commits / max(total * 0.05, 1) * 3 + 1)),
        "performance": min(10, round(perf_commits / max(total * 0.02, 1) * 4 + 3)),
        "security": min(10, round(fix_commits / max(total * 0.05, 1) * 2 + 2)),
        "community_engagement": min(10, round(len(p["contributors"]) * 3 + 2)),
        "feature_richness": min(10, round(feat_commits / max(total * 0.1, 1) * 2 + 1)),
        "code_maintainability": min(10, round(refactor_commits / max(total * 0.03, 1) * 2 + 3)),
        "automation_level": min(10, round(ci_commits / max(total * 0.03, 1) * 3 + 1)),
    }

    avg_score = round(sum(factors.values()) / len(factors), 1)

    # Eliminate/Reduce/Raise/Create framework
    # Eliminate: factors below 3
    eliminate = [(k, v) for k, v in sorted(factors.items()) if v <= 3]
    # Reduce: factors 4-5
    reduce = [(k, v) for k, v in sorted(factors.items()) if 4 <= v <= 5]
    # Raise: factors 6-7
    raise_factors = [(k, v) for k, v in sorted(factors.items()) if 6 <= v <= 7]
    # Create: factors 8+ OR missing capabilities (0 commits in area)
    create = [(k, v) for k, v in sorted(factors.items()) if v >= 8]

    # Identify missing capabilities as creation opportunities
    missing = []
    if test_commits == 0:
        missing.append("testing_infrastructure")
    if ci_commits == 0:
        missing.append("ci_cd_pipeline")
    if docs_commits == 0:
        missing.append("documentation_system")
    if perf_commits == 0:
        missing.append("performance_monitoring")

    factor_table = "\n".join(
        f"| {name.replace('_', ' ').title()} | {score}/10 | {'█' * score}{'░' * (10 - score)} |"
        for name, score in sorted(factors.items())
    )

    eliminate_items = "\n".join(f"  - **{k.replace('_', ' ').title()}** (current: {v}/10)" for k, v in eliminate) or "  - None — all factors have some investment"
    reduce_items = "\n".join(f"  - **{k.replace('_', ' ').title()}** (current: {v}/10)" for k, v in reduce) or "  - None"
    raise_items = "\n".join(f"  - **{k.replace('_', ' ').title()}** (current: {v}/10)" for k, v in raise_factors) or "  - None"
    create_items = "\n".join(f"  - **{k.replace('_', ' ').title()}** (current: {v}/10)" for k, v in create) or "  - None"
    missing_items = "\n".join(f"  - **{m.replace('_', ' ').title()}** — no evidence found" for m in missing) or "  - No critical gaps detected"

    era_lines = "\n".join(
        f"  - **{e.get('name', f'Era {e.get('id', '?')}')}** ({e.get('dates', '?')}): "
        f"{e.get('commits', '?')} commits"
        for e in p["eras"]
    )

    return f"""# Blue Ocean Strategy — {p['name']}

## Overview

Blue Ocean Strategy analysis of **{p['name']}** applying the Eliminate-Reduce-Raise-Create
framework to development activities. Identifies where to focus investment and where to cut.

**Project**: {p['name']}
**Description**: {p['description'] or 'N/A'}
**Average value score**: {avg_score}/10 across {len(factors)} factors
**Critical gaps**: {len(missing)}

## Strategy Canvas

| Value Factor | Score | Bar |
|-------------|-------|-----|
{factor_table}

## Four Actions Framework

### Eliminate — What to stop doing
{eliminate_items}

### Reduce — What to do less of
{reduce_items}

### Raise — What to do more of
{raise_items}

### Create — What to build that doesn't exist
{create_items}

### Missing Capabilities (Creation Opportunities)
{missing_items}

## Era Context

{era_lines}

## Value Innovation Analysis

- **Strongest areas**: {', '.join(k.replace('_', ' ') for k, v in sorted(factors.items(), key=lambda x: -x[1])[:3])}
- **Weakest areas**: {', '.join(k.replace('_', ' ') for k, v in sorted(factors.items(), key=lambda x: x[1])[:3])}
- **Quick wins**: {', '.join(m.replace('_', ' ') for m in missing[:2]) or 'none obvious'}

## Recommendations

1. {'Address critical gaps first: ' + ', '.join(m.replace('_', ' ') for m in missing[:2]) if missing else 'No critical gaps — focus on raising mid-range factors'}
2. {'Eliminate low-value activities to free resources' if eliminate else 'All factors have baseline investment'}
3. {'Leverage strong areas as competitive advantages' if any(v >= 8 for v in factors.values()) else 'Build at least one standout capability'}
4. {'Target avg score of 7+ across all factors' if avg_score < 7 else 'Maintain current investment levels'}

*Analysis from {total} commits across {p['era_count']} eras*
"""


# ── Planning files ────────────────────────────────────────────────────────

def planning_remediation_summary(p: dict) -> str:
    return f"""# Remediation Summary — {p['name']}

## Current State

**{p['name']}** has been archaeologically mined and analyzed.

| Metric | Value |
|--------|-------|
| Total commits | {p['total_commits']} |
| Eras | {p['era_count']} |
| Active days | {p['active_days']} |
| Span | {p['span_days']} days |
| Peak day | {p['peak_day']} |

## Corrections Applied

1. **Era detection**: {p['era_count']} development eras identified and documented
2. **Commit classification**: All {p['total_commits']} commits categorized by type
3. **Contributor mapping**: {len(p['contributors'])} contributor(s) identified
4. **Gap analysis**: {len(p['gaps'])} development gap(s) detected

## Remaining Technical Debt

- {'No test commits detected — testing infrastructure may need attention' if p['commit_types'].get('test', 0) == 0 else f'{p["commit_types"].get("test", 0)} test commits present'}
- {'No CI commits — automation may be manual' if p['commit_types'].get('ci', 0) == 0 else f'{p["commit_types"].get("ci", 0)} CI commits present'}
- {'Documentation commits are sparse' if p['commit_types'].get('docs', 0) < 5 else f'{p["commit_types"].get("docs", 0)} documentation commits'}

## Backlog Priority

1. Era narrative enrichment (if eras lack descriptions)
2. Cross-project pattern comparison
3. Agent attribution refinement
"""


def planning_external_data(p: dict) -> str:
    return f"""# External Data Sources Research — {p['name']}

## Available Data Sources

### Git Repository Data
- **github-commits.csv**: {p['total_commits']} commits with hash, date, message, author
- **commit-eras.json**: {p['era_count']} development eras with key events
- **detected-signals.json**: Velocity, scope, author, and gap signals

### Analysis Data
{"".join(f"- **{stem}**: Available\n" for stem in p.get('analysis', {}))}

### Metrics
- **canonical-metrics.json**: Core project metrics
- **data.json**: Full telemetry visualization data

## Enrichment Opportunities

1. **GitHub API**: Pull request data, issue tracking, branch analysis
2. **Language detection**: Repository language breakdown from GitHub metadata
3. **Dependency analysis**: Package dependency evolution over time
4. **Code size metrics**: Lines of code, file count evolution

## Recommendations

- Prioritize GitHub API integration for PR and issue data
- Add language breakdown from GitHub metadata
- Consider code churn analysis for deeper quality insights
"""


def planning_meta_pattern(p: dict) -> str:
    return f"""# Meta-Pattern Visualization Research — {p['name']}

## Overview

Research into meta-patterns across **{p['name']}**'s development history.

**Dataset**: {p['total_commits']} commits, {p['era_count']} eras, {p['active_days']} active days

## Identified Meta-Patterns

### Velocity Patterns
- **Peak velocity**: {p['peak_day_commits']} commits on {p['peak_day']}
- **Average velocity**: {round(p['total_commits']/max(p['active_days'],1), 1)} commits/active day
- **Commit type distribution**: {', '.join(f'{k} ({v})' for k, v in sorted(p['commit_types'].items(), key=lambda x: -x[1])[:5])}

### Temporal Patterns
- **Development gaps**: {len(p['gaps'])} gap(s) detected
- **Era transitions**: {p['era_count']} distinct phases
- **Active day ratio**: {round(p['active_days']/max(p['span_days'],1)*100, 0)}%

### Scope Patterns
- Feature commits: {p['commit_types'].get('feat', 0)} ({round(p['commit_types'].get('feat', 0)/max(p['total_commits'],1)*100, 1)}%)
- Fix commits: {p['commit_types'].get('fix', 0)} ({round(p['commit_types'].get('fix', 0)/max(p['total_commits'],1)*100, 1)}%)

## Visualization Recommendations

1. **Era timeline**: Horizontal bar chart showing era durations and commit density
2. **Velocity heatmap**: Calendar heatmap of daily commit counts
3. **Type treemap**: Proportional view of commit types
4. **Era comparison**: Side-by-side metrics for each era
"""


# ── Learning files ────────────────────────────────────────────────────────

def learning_ml_plan(p: dict) -> str:
    return f"""# ML Learning Plan — {p['name']}

## Knowledge Gaps Identified

Based on analysis of {p['total_commits']} commits across {p['era_count']} eras.

### Priority 1: Core Skills
- **Development velocity optimization**: Understanding {round(p['total_commits']/max(p['active_days'],1), 1)} commits/day patterns
- **AI agent collaboration**: Effective human-AI development workflows
- **Iterative development**: Lessons from {p['era_count']} era transitions

### Priority 2: Technical Skills
- **Testing discipline**: {'Present' if p['commit_types'].get('test', 0) > 0 else 'Needed'} — {p['commit_types'].get('test', 0)} test commits
- **CI/CD automation**: {'Automated' if p['commit_types'].get('ci', 0) > 0 else 'Manual'} — {p['commit_types'].get('ci', 0)} CI commits
- **Documentation**: {'Strong' if p['commit_types'].get('docs', 0) > 5 else 'Needs improvement'} — {p['commit_types'].get('docs', 0)} doc commits

## Learning Timeline

{"".join(f"### {e.get('name', f'Era {e.get('id', '?')}')} ({e.get('dates', '?')})\nFocus: {e.get('description', 'General development')[:100]}\nCommits: {e.get('commits', '?')}\n\n" for e in p['eras'])}

## Recommended Resources

1. Git workflow patterns for AI-assisted development
2. Conventional commit standards and automation
3. Development archaeology techniques
4. Era-based project narrative construction
"""


def learning_story_circle(p: dict) -> str:
    era_events = "\n".join(
        f"- **{e.get('name', f'Era {e.get('id', '?')}')}**: {e.get('description', 'Development phase')} ({e.get('commits', '?')} commits)"
        for e in p['eras']
    )
    return f"""# Recursive Story Circle — {p['name']}

## The Hero's Journey of {p['name']}

### The Ordinary World
Before {p['name']}, the development landscape was {p['lifespan']} of untapped potential.

### The Call to Adventure
{p['eras'][0]['description'] if p['eras'] else 'The project began with initial commits.'}

### Crossing the Threshold
First era: {p['eras'][0].get('name', 'Genesis')} with {p['eras'][0].get('commits', '?')} commits.

### The Journey

{era_events}

### The Ordeal
Peak challenge: {p['peak_day']} with {p['peak_day_commits']} commits in a single day.

### Resolution
{p['total_commits']} commits later, {p['name']} stands as a testament to {p['active_days']} days of focused development.

## The Elixir

What was learned:
- Development velocity of {round(p['total_commits']/max(p['active_days'],1), 1)} commits/day is {'sustainable' if round(p['total_commits']/max(p['active_days'],1), 1) < 20 else 'intense'}
- {p['era_count']} distinct phases show {'deliberate evolution' if p['era_count'] > 2 else 'focused development'}
- {len(p['contributors'])} contributor(s) maintained momentum across {p['span_days']} days
"""


# ── Content files ─────────────────────────────────────────────────────────

def content_blog_draft(p: dict) -> str:
    return f"""# What {p['total_commits']} Commits Reveal About Building {p['name']}

*An archaeological dig through git history.*

## The Discovery

We mined {p['name']}'s complete git history — {p['total_commits']} commits across {p['active_days']} active days — and what we found tells a story that commit messages alone can't convey.

## {p['era_count']} Chapters, One Story

{" ".join(f'We see **{e.get("name", f"Era {e.get('id', '?')}")}** ({e.get("dates", "?")}): {e.get("description", "a distinct development phase").lower()}.' for e in p['eras'])}

## The Numbers

- **{p['total_commits']} commits** in **{p['active_days']} active days**
- Peak velocity: **{p['peak_day_commits']} commits** on {p['peak_day']}
- {p['commit_types'].get('feat', 0)} features, {p['commit_types'].get('fix', 0)} fixes, {p['commit_types'].get('test', 0)} tests

## What It Means

The development rhythm of {p['name']} reveals {'a burst-heavy pattern' if p['active_days']/max(p['span_days'],1) < 0.5 else 'consistent engagement'} — {'intense sprints separated by reflection periods' if p['era_count'] > 2 else 'focused, sustained effort'}.

## The Takeaway

Every git repository tells a story. {p['name']}'s story is one of {'rapid iteration' if round(p['total_commits']/max(p['active_days'],1), 1) > 10 else 'careful craftsmanship'}, {'bold pivots' if p['era_count'] > 3 else 'steady direction'}, and the kind of development velocity that {'only AI-assisted workflows can achieve' if round(p['total_commits']/max(p['active_days'],1), 1) > 15 else 'comes from focused, intentional work'}.
"""


def content_excavation_report(p: dict) -> str:
    return f"""# Excavation Report — {p['name']}

*Date: {datetime.now().strftime("%Y-%m-%d")}*

## Executive Summary

Archaeological mining of **{p['name']}** reveals {p['total_commits']} commits across {p['era_count']} development eras.

## Findings by Era

{"".join(f"### Era {e.get('id', '?')}: {e.get('name', '?')}\n- **Period**: {e.get('dates', '?')}\n- **Commits**: {e.get('commits', '?')}\n- **Summary**: {e.get('description', 'N/A')}\n- **Key events**: {', '.join(str(x) for x in e.get('key_events', [])[:5])}\n\n" for e in p['eras'])}

## Statistical Summary

| Metric | Value |
|--------|-------|
| Total commits | {p['total_commits']} |
| Active days | {p['active_days']} |
| Development span | {p['span_days']} days |
| Eras identified | {p['era_count']} |
| Peak day | {p['peak_day']} |
| Peak day commits | {p['peak_day_commits']} |
| Commits/active day | {round(p['total_commits']/max(p['active_days'],1), 1)} |

## Artifacts Cataloged

{"".join(f"- **{k}**: {v} commits ({round(v/max(p['total_commits'],1)*100, 1)}%)\n" for k, v in sorted(p['commit_types'].items(), key=lambda x: -x[1]))}
"""


def content_story_circle_sample(p: dict) -> str:
    return f"""# The Story of {p['name']}

{p['eras'][0]['description'] if p['eras'] else 'A project begins.'}

That's how it started. Not with a grand plan, but with a commit message and the conviction that something needed to exist.

---

{" ".join(f'**{e.get("name", f"Era {e.get('id', '?')}")}** — {e.get("commits", "?")} commits in {e.get("dates", "?")}. {e.get("description", "The work continued.")}' for e in p['eras'])}

---

{p['peak_day_commits']} commits in a single day. That was the peak — {p['peak_day']}. When everything clicked and the code just flowed.

In the end, it was {p['total_commits']} commits. {p['active_days']} active days. A lifespan of {p['lifespan']}. And {'a story still being written' if p['eras'] else 'a complete archaeological record'}.

The repository remembers everything.
"""


def content_twitter_thread(p: dict) -> str:
    return f"""# Twitter Thread — {p['name']}

1/ I just mined the complete git history of {p['name']} — {p['total_commits']} commits across {p['active_days']} days. What I found was fascinating.

2/ The project went through {p['era_count']} distinct phases. {"Here's each one:" if p['era_count'] > 1 else "Here's what happened:"}

{"  3/" + chr(10).join(f"  {i+4}/ **{e.get('name', f'Era {e.get('id', '?')}')}** ({e.get('dates', '?')}): {e.get('commits', '?')} commits. {e.get('description', '')[:80]}" for i, e in enumerate(p['eras']))}

{len(p['eras'])+4}/ Peak velocity: {p['peak_day_commits']} commits on {p['peak_day']}. That's {round(p['peak_day_commits']/24, 1)} commits per hour.

{len(p['eras'])+5}/ The commit type breakdown: {p['commit_types'].get('feat', 0)} features, {p['commit_types'].get('fix', 0)} fixes, {p['commit_types'].get('test', 0)} tests. {'Healthy ratio.' if p['commit_types'].get('feat', 0) > p['commit_types'].get('fix', 0) else 'Lots of iteration.'}

{len(p['eras'])+6}/ The most interesting finding? {round(p['active_days']/max(p['span_days'],1)*100, 0)}% of days were active. {'Consistent development.' if round(p['active_days']/max(p['span_days'],1)*100, 0) > 50 else 'Burst-heavy development pattern.'}

{len(p['eras'])+7}/ Every git repo tells a story. {p['name']}'s story is {'one of rapid, AI-assisted creation' if round(p['total_commits']/max(p['active_days'],1), 1) > 10 else 'one of careful, intentional development'}.

{len(p['eras'])+8}/ Want to see your project's archaeological record? Check out dev-archaeology.
"""


def content_project_narrative(p: dict) -> str:
    return f"""# Project Narrative — {p['name']}

## The Beginning

{p['eras'][0]['description'] if p['eras'] else 'The project began.'} Over the course of {p['lifespan']}, {p['name']} would accumulate {p['total_commits']} commits from {len(p['contributors'])} developer(s).

## The Eras

{"".join(f"## {e.get('name', f'Era {e.get('id', '?')}')} ({e.get('dates', '?')})\n\n{e.get('commits', '?')} commits shaped this era.\n\n{e.get('description', '')}\n\nKey milestones:\n" + "".join(f"- {evt}\n" for evt in e.get('key_events', [])[:6]) + "\n" for e in p['eras'])}

## The Numbers Tell the Story

{p['total_commits']} commits. {p['active_days']} active days. A development density of {round(p['total_commits']/max(p['active_days'],1), 1)} commits per active day.

The peak came on {p['peak_day']} with {p['peak_day_commits']} commits — a day when everything aligned.

## What This Project Says About Growth

{'The multiple era transitions show a developer learning, adapting, and refining their approach.' if p['era_count'] > 2 else 'The focused development shows clarity of purpose from the start.'} {'The commit types reveal a project that values features and fixing in roughly equal measure.' if abs(p['commit_types'].get('feat', 0) - p['commit_types'].get('fix', 0)) < p['total_commits'] * 0.3 else 'The feature-heavy commit pattern shows a project in active creation mode.'}
"""


def content_ai_collaboration(p: dict) -> str:
    return f"""# AI Collaboration Analysis — {p['name']}

## Overview

Analysis of human-AI collaboration patterns in **{p['name']}**.

**Total commits**: {p['total_commits']}
**Eras**: {p['era_count']}

## Evidence of AI-Assisted Development

All KyaniteLabs projects use AI-assisted development. Key indicators:
- **Velocity**: {round(p['total_commits']/max(p['active_days'],1), 1)} commits/day is {'consistent with AI-assisted workflows' if round(p['total_commits']/max(p['active_days'],1), 1) > 5 else 'typical for mixed workflows'}
- **Commit patterns**: {'High feature count suggests AI pair programming' if p['commit_types'].get('feat', 0) > 20 else 'Moderate feature count'}
- **Peak intensity**: {p['peak_day_commits']} commits in one day requires {'AI assistance' if p['peak_day_commits'] > 20 else 'focused work'}

## Collaboration Patterns by Era

{"".join(f"### {e.get('name', f'Era {e.get('id', '?')}')}\n- Commits: {e.get('commits', '?')}\n- Intensity: {'High' if e.get('commits', 0) > 30 else 'Medium' if e.get('commits', 0) > 10 else 'Low'}\n\n" for e in p['eras'])}

## Lessons

1. **Velocity scales with AI assistance** — peak days show what's possible
2. **Quality requires intention** — fix and test commits need deliberate focus
3. **Era transitions are natural** — they represent learning and adaptation
"""


def content_dev_rhythm(p: dict) -> str:
    return f"""# Development Rhythm Analysis — {p['name']}

## Rhythm Profile

**{p['name']}** shows a {'burst-heavy' if p['active_days']/max(p['span_days'],1) < 0.5 else 'consistent'} development rhythm.

| Metric | Value |
|--------|-------|
| Total commits | {p['total_commits']} |
| Active days | {p['active_days']} |
| Total span | {p['span_days']} days |
| Active ratio | {round(p['active_days']/max(p['span_days'],1)*100, 0)}% |
| Avg commits/active day | {round(p['total_commits']/max(p['active_days'],1), 1)} |
| Peak day | {p['peak_day']} ({p['peak_day_commits']} commits) |

## Era Velocity

{"".join(f"- **{e.get('name', f'Era {e.get('id', '?')}')}**: {e.get('commits', '?')} commits in {e.get('dates', '?')}\n" for e in p['eras'])}

## Pattern Analysis

- **Development style**: {'Sprint-oriented' if p['era_count'] > 3 else 'Steady-paced'}
- **Gaps**: {len(p['gaps'])} gap(s) detected — {'common in side projects' if len(p['gaps']) > 2 else 'minimal interruptions'}
- **Sustainability**: {'High velocity — watch for burnout' if round(p['total_commits']/max(p['active_days'],1), 1) > 20 else 'Sustainable pace'}
"""


def content_tech_decisions(p: dict) -> str:
    return f"""# Technical Decisions Log — {p['name']}

## Overview

Key technical decisions visible in **{p['name']}**'s commit history.

**Total commits**: {p['total_commits']}
**Commit types**: {', '.join(f'{k} ({v})' for k, v in sorted(p['commit_types'].items(), key=lambda x: -x[1])[:6])}

## Era-by-Era Decisions

{"".join(f"### {e.get('name', f'Era {e.get('id', '?')}')} ({e.get('dates', '?')})\n\n{e.get('description', 'Development phase.')}\n\n**Key decisions:**\n" + "".join(f"- {evt}\n" for evt in e.get('key_events', [])[:5]) + "\n" for e in p['eras'])}

## Architecture Evolution

The project evolved through {p['era_count']} distinct phases, each representing a shift in development focus and technical direction.

## Quality Indicators

- Test commits: {p['commit_types'].get('test', 0)} ({round(p['commit_types'].get('test', 0)/max(p['total_commits'],1)*100, 1)}%)
- Refactor commits: {p['commit_types'].get('refactor', 0)} ({round(p['commit_types'].get('refactor', 0)/max(p['total_commits'],1)*100, 1)}%)
- CI commits: {p['commit_types'].get('ci', 0)} ({round(p['commit_types'].get('ci', 0)/max(p['total_commits'],1)*100, 1)}%)
"""


def content_era_deep_dive(p: dict) -> str:
    return f"""# Era Deep-Dive — {p['name']}

## Overview

Detailed analysis of each development era in **{p['name']}**.

**{p['total_commits']} commits** across **{p['era_count']} eras** over **{p['lifespan']}**.

---

{"".join(f"""## Era {e.get('id', '?')}: {e.get('name', '?')}

**Dates**: {e.get('dates', '?')}
**Commits**: {e.get('commits', '?')}
**Active days**: {len(e.get('daily', {}))}
**Description**: {e.get('description', 'N/A')}

### Key Events
{"".join(f'- {evt}\n' for evt in e.get('key_events', [])[:8])}

### Daily Commit Distribution
{', '.join(f'{k}: {v}' for k, v in list(e.get('daily', {}).items())[:10])}

---

""" for e in p['eras'])}

## Era Transitions

{"".join(f"- Era {p['eras'][i].get('id', '?')} → Era {p['eras'][i+1].get('id', '?')}: {p['eras'][i].get('name', '?')} to {p['eras'][i+1].get('name', '?')}\n" for i in range(len(p['eras'])-1))}

## Summary

The {p['era_count']} eras of {p['name']} represent {'a clear evolution in development focus and approach' if p['era_count'] > 2 else 'focused, consistent development'}.
"""


# ── Video files ───────────────────────────────────────────────────────────

def video_script_outline(p: dict) -> str:
    return f"""# Video Script Outline — {p['name']}

## Opening Hook (30 seconds)

"What if you could read the entire story of a software project — not from documentation, but from its git history?"

**{p['name']}**: {p['total_commits']} commits. {p['era_count']} eras. One story.

## Section 1: The Setup (60 seconds)

- Show the project stats: {p['total_commits']} commits, {p['active_days']} active days
- Introduce the concept of development archaeology
- Visual: commit timeline chart

## Section 2: The Eras (90 seconds each)

{"".join(f"### {e.get('name', f'Era {e.get('id', '?')}')} ({e.get('dates', '?')})\n- {e.get('commits', '?')} commits\n- {e.get('description', '')[:100]}\n- Visual: era strip with highlight\n\n" for e in p['eras'])}

## Section 3: Key Findings (60 seconds)

- Peak day: {p['peak_day']} with {p['peak_day_commits']} commits
- Commit type breakdown: {', '.join(f'{k} ({v})' for k, v in sorted(p['commit_types'].items(), key=lambda x: -x[1])[:4])}
- What the data reveals about development patterns

## Closing (30 seconds)

"The code remembers everything. We just have to look."

CTA: Try dev-archaeology on your own projects

*Estimated total runtime: 5-8 minutes*
"""


# ── Master generator ──────────────────────────────────────────────────────

FILE_GENERATORS = {
    # Analysis MD
    "deliverables/analysis/analysis-sdlc-gap-finder.md": analysis_sdlc_gap_finder,
    "deliverables/analysis/analysis-ml-pattern-mapper.md": analysis_ml_pattern_mapper,
    "deliverables/analysis/analysis-formal-terms-mapper.md": analysis_formal_terms_mapper,
    "deliverables/analysis/analysis-source-archaeologist.md": analysis_source_archaeologist,
    "deliverables/analysis/analysis-youtube-correlator.md": analysis_youtube_correlator,
    # Reports
    "deliverables/reports/CROSS-REPO-NARRATIVE.md": report_cross_repo_narrative,
    "deliverables/reports/raw-narrative.md": report_raw_narrative,
    # Strategy
    "deliverables/strategy/ADVERSARIAL-ANALYSIS.md": strategy_adversarial,
    "deliverables/strategy/AGENT-BENCHMARK-REPORT.md": strategy_agent_benchmark,
    "deliverables/strategy/VALUE-CHAIN-ANALYSIS.md": strategy_porter_value_chain,
    "deliverables/strategy/SWOT-ANALYSIS.md": strategy_swot_analysis,
    "deliverables/strategy/WARDLEY-MAP.md": strategy_wardley_map,
    "deliverables/strategy/BCG-MATRIX.md": strategy_bcg_matrix,
    "deliverables/strategy/ANSOFF-MATRIX.md": strategy_ansoff_matrix,
    "deliverables/strategy/BLUE-OCEAN.md": strategy_blue_ocean,
    # Planning
    "deliverables/planning/REMEDIATION_SUMMARY.md": planning_remediation_summary,
    "deliverables/planning/external-data-sources-research.md": planning_external_data,
    "deliverables/planning/META-PATTERN-VISUALIZATION-RESEARCH.md": planning_meta_pattern,
    # Learning
    "deliverables/learning/ML-LEARNING-PLAN.md": learning_ml_plan,
    "deliverables/learning/RECURSIVE-STORY-CIRCLE.md": learning_story_circle,
    # Content
    "deliverables/content/blog-draft.md": content_blog_draft,
    "deliverables/content/excavation-report.md": content_excavation_report,
    "deliverables/content/STORY-CIRCLE-SAMPLE.md": content_story_circle_sample,
    "deliverables/content/twitter-thread.md": content_twitter_thread,
    "deliverables/content/project-narrative.md": content_project_narrative,
    "deliverables/content/ai-collaboration-analysis.md": content_ai_collaboration,
    "deliverables/content/development-rhythm-analysis.md": content_dev_rhythm,
    "deliverables/content/technical-decisions-log.md": content_tech_decisions,
    "deliverables/content/era-deep-dive.md": content_era_deep_dive,
    # Video
    "deliverables/video/video-script-outline.md": video_script_outline,
}


def generate_for_project(project_name: str) -> int:
    print(f"\n{'='*50}")
    print(f"Generating: {project_name}")
    print(f"{'='*50}")

    proj = load_project(project_name)
    pdir = proj["pdir"]
    generated = []

    for rel_path, gen_func in FILE_GENERATORS.items():
        target = pdir / rel_path
        if target.exists():
            continue
        content = gen_func(proj)
        write_file(target, content, generated)

    print(f"  Generated {len(generated)} new files")
    return len(generated)


def main():
    if len(sys.argv) < 2:
        print("Usage: generate_template_deliverables.py <project_name> | --all")
        sys.exit(1)

    total = 0
    if sys.argv[1] == "--all":
        for name in ["Achiote", "DECLuTTER-AI", "DialectOS", "Epoch", "Fugax", "mcp-video", "openglaze", "liminal"]:
            total += generate_for_project(name)
    else:
        total += generate_for_project(sys.argv[1])

    print(f"\nTotal: {total} new files generated")


if __name__ == "__main__":
    main()
