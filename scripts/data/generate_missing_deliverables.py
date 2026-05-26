#!/usr/bin/env python3
"""Generate all missing deliverables for KyaniteLabs projects.

Uses local LLM (qwen3.6-27b on LM Studio) to generate narrative content
based on real project data (commits, eras, analysis JSON, metrics).

Usage:
    python3 scripts/data/generate_missing_deliverables.py <project_name>
    python3 scripts/data/generate_missing_deliverables.py --all
"""

import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
LM_STUDIO_URL = os.environ.get("LM_STUDIO_URL", "http://localhost:1234")
MODEL = os.environ.get("LM_MODEL", "qwen3.6-27b")


def load_project_data(project_name: str) -> dict:
    """Load all available data for a project."""
    pdir = ROOT / "projects" / project_name
    data = {"name": project_name}

    # Project config
    config_path = pdir / "project.json"
    if config_path.exists():
        data["config"] = json.loads(config_path.read_text(encoding="utf-8"))

    # Commit eras
    eras_path = pdir / "data" / "commit-eras.json"
    if eras_path.exists():
        eras_data = json.loads(eras_path.read_text(encoding="utf-8"))
        data["eras"] = eras_data.get("eras", [])
        data["total_commits"] = eras_data.get("total_commits", 0)
        data["contributors"] = eras_data.get("contributors", [])
        data["commit_types"] = eras_data.get("commit_types", {})
        data["daily_frequency"] = eras_data.get("daily_commit_frequency", {})
        data["gaps"] = eras_data.get("gaps", [])

    # Canonical metrics
    metrics_path = pdir / "deliverables" / "canonical-metrics.json"
    if metrics_path.exists():
        data["metrics"] = json.loads(metrics_path.read_text(encoding="utf-8"))

    # Data.json for chart data
    data_json_path = pdir / "deliverables" / "data.json"
    if data_json_path.exists():
        data["data_json"] = json.loads(data_json_path.read_text(encoding="utf-8"))

    # Analysis JSON files
    analysis_dir = pdir / "deliverables" / "analysis"
    data["analysis"] = {}
    if analysis_dir.exists():
        for f in analysis_dir.glob("*.json"):
            data["analysis"][f.stem] = json.loads(f.read_text(encoding="utf-8"))

    return data


def llm_generate(prompt: str, max_tokens: int = 4000) -> str:
    """Generate text using local LLM via LM Studio."""
    payload = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "top_p": 0.9,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{LM_STUDIO_URL}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"ERROR: LLM generation failed: {e}"


def build_context(proj: dict) -> str:
    """Build a context string from project data for LLM prompts."""
    lines = [f"Project: {proj['name']}"]
    if "config" in proj:
        lines.append(f"Description: {proj['config'].get('description', 'N/A')}")
    if "total_commits" in proj:
        lines.append(f"Total commits: {proj['total_commits']}")
    if "metrics" in proj:
        m = proj["metrics"]
        lines.append(f"Active days: {m.get('active_days', '?')}")
        lines.append(f"Span: {m.get('span_days', '?')} days")
        lines.append(f"Peak day: {m.get('peak_day', '?')} ({m.get('peak_day_commits', '?')} commits)")
    if "eras" in proj:
        lines.append(f"Eras ({len(proj['eras'])}):")
        for era in proj["eras"]:
            lines.append(f"  - Era {era.get('id', '?')}: {era.get('name', '?')} ({era.get('dates', '?')}) — {era.get('commits', '?')} commits")
            if era.get("key_events"):
                for evt in era["key_events"][:3]:
                    lines.append(f"    • {evt}")
    if "commit_types" in proj:
        lines.append(f"Commit types: {json.dumps(proj['commit_types'])}")
    if "contributors" in proj:
        for c in proj["contributors"][:3]:
            lines.append(f"Contributor: {c.get('name', '?')} — {c.get('commits', '?')} commits ({c.get('percentage', '?')}%)")
    return "\n".join(lines)


def ensure_analysis_md(proj: dict) -> int:
    """Generate .md summaries for all analysis JSON files."""
    count = 0
    analysis_dir = ROOT / "projects" / proj["name"] / "deliverables" / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    for stem, data in proj.get("analysis", {}).items():
        md_path = analysis_dir / f"{stem}.md"
        if md_path.exists():
            continue

        prompt = f"""Generate a concise markdown analysis summary from this JSON data for the project "{proj['name']}".

Project context:
{build_context(proj)}

Analysis data ({stem}):
{json.dumps(data, indent=2)[:3000]}

Write a markdown summary with:
- A title (# {stem})
- Overview paragraph
- Key findings (bulleted)
- Implications for the project

Keep it factual and data-driven. Use real numbers from the JSON. Do not invent data."""

        content = llm_generate(prompt, max_tokens=2000)
        if not content.startswith("ERROR:"):
            # Clean up any thinking tags from reasoning models
            content = re.sub(r'<think[^>]*>.*?</think\s*>', '', content, flags=re.DOTALL).strip()
            md_path.write_text(content, encoding="utf-8")
            count += 1
            print(f"    + {md_path.name}")
            time.sleep(0.5)  # Rate limit

    return count


def ensure_report_files(proj: dict) -> int:
    """Generate missing report files."""
    count = 0
    reports_dir = ROOT / "projects" / proj["name"] / "deliverables" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # CROSS-REPO-NARRATIVE.md
    target = reports_dir / "CROSS-REPO-NARRATIVE.md"
    if not target.exists():
        prompt = f"""Generate a cross-repository narrative for "{proj['name']}".

Project context:
{build_context(proj)}

Write a markdown document titled "Cross-Repository Narrative" that:
- Places this project in the context of the KyaniteLabs ecosystem
- Describes how this project relates to other projects in the org
- Identifies shared patterns, technologies, and development approaches
- Discusses the project's role in the overall development trajectory

Use real data (commits, eras, dates). Keep it factual."""

        content = llm_generate(prompt, max_tokens=2000)
        if not content.startswith("ERROR:"):
            content = re.sub(r'<think[^>]*>.*?</think\s*>', '', content, flags=re.DOTALL).strip()
            target.write_text(content, encoding="utf-8")
            count += 1
            print(f"    + {target.name}")
            time.sleep(0.5)

    # raw-narrative.md
    target = reports_dir / "raw-narrative.md"
    if not target.exists():
        prompt = f"""Generate a raw chronological narrative for "{proj['name']}" from its commit history.

Project context:
{build_context(proj)}

Write a markdown document that tells the chronological story of this project's development:
- Go era by era, describing what was built and when
- Use actual commit messages and dates
- Capture the development flow and momentum shifts
- Be narrative but factual — no invented details

Title: "Raw Development Narrative — {proj['name']}" """

        content = llm_generate(prompt, max_tokens=3000)
        if not content.startswith("ERROR:"):
            content = re.sub(r'<think[^>]*>.*?</think\s*>', '', content, flags=re.DOTALL).strip()
            target.write_text(content, encoding="utf-8")
            count += 1
            print(f"    + {target.name}")
            time.sleep(0.5)

    return count


def ensure_strategy_files(proj: dict) -> int:
    """Generate missing strategy files."""
    count = 0
    strategy_dir = ROOT / "projects" / proj["name"] / "deliverables" / "strategy"
    strategy_dir.mkdir(parents=True, exist_ok=True)

    missing = {
        "ADVERSARIAL-ANALYSIS.md": f"""Generate an adversarial analysis for "{proj['name']}".

Project context:
{build_context(proj)}

Write a markdown document that critically examines this project:
- What assumptions might be wrong?
- What are the weakest aspects of the codebase?
- What technical debt is accumulating?
- What would a critic say about the development approach?
- Rate confidence levels for key claims

Be honest and constructive. Title: "Adversarial Analysis — {proj['name']}" """,

        "AGENT-BENCHMARK-REPORT.md": f"""Generate an agent benchmark report for "{proj['name']}".

Project context:
{build_context(proj)}

Write a markdown document analyzing AI agent usage in this project:
- Which AI agents were used (Claude Code, Cursor, etc.)
- How effective was AI-assisted development?
- What patterns of agent usage emerged?
- Quality comparison between agent-assisted and manual commits
- Recommendations for improving AI-assisted workflow

Title: "Agent Benchmark Report — {proj['name']}" """,
    }

    for filename, prompt in missing.items():
        target = strategy_dir / filename
        if target.exists():
            continue

        content = llm_generate(prompt, max_tokens=2500)
        if not content.startswith("ERROR:"):
            content = re.sub(r'<think[^>]*>.*?</think\s*>', '', content, flags=re.DOTALL).strip()
            target.write_text(content, encoding="utf-8")
            count += 1
            print(f"    + {target.name}")
            time.sleep(0.5)

    return count


def ensure_planning_files(proj: dict) -> int:
    """Generate missing planning files."""
    count = 0
    planning_dir = ROOT / "projects" / proj["name"] / "deliverables" / "planning"
    planning_dir.mkdir(parents=True, exist_ok=True)

    missing = {
        "REMEDIATION_SUMMARY.md": f"""Generate a remediation summary for "{proj['name']}".

Project context:
{build_context(proj)}

Write a markdown document summarizing:
- What architectural corrections have been made
- What technical debt remains
- What naming/terminology fixes were applied
- Current state of code quality
- Prioritized remediation backlog

Title: "Remediation Summary — {proj['name']}" """,

        "external-data-sources-research.md": f"""Generate an external data sources research document for "{proj['name']}".

Project context:
{build_context(proj)}

Write a markdown document identifying:
- External APIs or data sources this project depends on
- What data enrichment opportunities exist
- Rate limits, costs, and reliability considerations
- Recommended data sources for deeper analysis

Title: "External Data Sources Research — {proj['name']}" """,

        "META-PATTERN-VISUALIZATION-RESEARCH.md": f"""Generate a meta-pattern visualization research document for "{proj['name']}".

Project context:
{build_context(proj)}

Write a markdown document exploring:
- What meta-patterns exist in this project's development history
- How velocity, scope, and author patterns interact
- What visualization approaches would best reveal these patterns
- Recommendations for advanced analysis techniques

Title: "Meta-Pattern Visualization Research — {proj['name']}" """,
    }

    for filename, prompt in missing.items():
        target = planning_dir / filename
        if target.exists():
            continue

        content = llm_generate(prompt, max_tokens=2000)
        if not content.startswith("ERROR:"):
            content = re.sub(r'<think[^>]*>.*?</think\s*>', '', content, flags=re.DOTALL).strip()
            target.write_text(content, encoding="utf-8")
            count += 1
            print(f"    + {target.name}")
            time.sleep(0.5)

    return count


def ensure_learning_files(proj: dict) -> int:
    """Generate missing learning files."""
    count = 0
    learning_dir = ROOT / "projects" / proj["name"] / "deliverables" / "learning"
    learning_dir.mkdir(parents=True, exist_ok=True)

    missing = {
        "ML-LEARNING-PLAN.md": f"""Generate an ML-focused learning plan for "{proj['name']}".

Project context:
{build_context(proj)}

Write a markdown document that:
- Identifies ML/AI knowledge gaps exposed by this project
- Creates a prioritized learning plan based on what the project actually needed
- Maps specific commits to learning topics
- Suggests resources and exercises
- Focuses on practical, project-relevant skills

Title: "ML Learning Plan — {proj['name']}" """,

        "RECURSIVE-STORY-CIRCLE.md": f"""Generate a recursive story circle document for "{proj['name']}".

Project context:
{build_context(proj)}

Write a markdown document that frames the project's development as a narrative arc:
- The ordinary world (what came before the project)
- The call to adventure (why the project started)
- Crossing the threshold (first significant commits)
- Tests, allies, enemies (technical challenges)
- The ordeal (biggest challenge/peak)
- Reward, road back, resurrection (resolution)
- Return with elixir (what was learned)

Use real dates, commits, and events. Title: "Recursive Story Circle — {proj['name']}" """,
    }

    for filename, prompt in missing.items():
        target = learning_dir / filename
        if target.exists():
            continue

        content = llm_generate(prompt, max_tokens=2000)
        if not content.startswith("ERROR:"):
            content = re.sub(r'<think[^>]*>.*?</think\s*>', '', content, flags=re.DOTALL).strip()
            target.write_text(content, encoding="utf-8")
            count += 1
            print(f"    + {target.name}")
            time.sleep(0.5)

    return count


def ensure_content_files(proj: dict) -> int:
    """Generate missing content files."""
    count = 0
    content_dir = ROOT / "projects" / proj["name"] / "deliverables" / "content"
    content_dir.mkdir(parents=True, exist_ok=True)

    missing = {
        "blog-draft.md": f"""Generate a blog post draft about "{proj['name']}".

Project context:
{build_context(proj)}

Write a compelling blog post (800-1200 words) about this project:
- Hook the reader with an interesting angle from the actual development data
- Tell the story of how the project evolved
- Include real numbers (commits, timeline, patterns)
- Discuss what makes this project interesting from a development archaeology perspective
- End with a takeaway or lesson learned

Title should be engaging. Write in first-person plural ("we").""",

        "excavation-report.md": f"""Generate an excavation report for "{proj['name']}".

Project context:
{build_context(proj)}

Write a markdown excavation report:
- What was discovered by mining the git history
- Key findings from each era
- Notable patterns in commit messages, timing, and scope
- What the data reveals about development practices
- Summary statistics and their meaning

Title: "Excavation Report — {proj['name']}" """,

        "STORY-CIRCLE-SAMPLE.md": f"""Generate a story circle sample for "{proj['name']}".

Project context:
{build_context(proj)}

Write a short narrative piece (500-800 words) that tells the project's story
in an engaging, almost literary way:
- Use the development timeline as a narrative structure
- Weave in real commit messages as dialogue or events
- Make the code feel alive
- Focus on the human side of development

Title: "The Story of {proj['name']}" """,

        "twitter-thread.md": f"""Generate a Twitter/X thread about "{proj['name']}".

Project context:
{build_context(proj)}

Write a 8-12 tweet thread about this project's development story:
- Start with a hook
- Each tweet is one key insight or moment
- Include real numbers and dates
- End with a provocative question or takeaway
- Use engaging but professional tone

Format as numbered tweets (1/, 2/, etc.)""",

        f"project-narrative-{proj['name'].lower()}.md": f"""Generate a project narrative for "{proj['name']}".

Project context:
{build_context(proj)}

Write a longer-form narrative (1000-1500 words) about this project:
- Chapter-style breakdown of each era
- What was built, why it mattered
- Technical decisions and their consequences
- The overall arc of development
- What this project says about the developer's growth

Title: "Project Narrative — {proj['name']}" """,

        "ai-collaboration-analysis.md": f"""Generate an AI collaboration analysis for "{proj['name']}".

Project context:
{build_context(proj)}

Write a markdown analysis of how AI agents were used in this project:
- Evidence of AI-assisted commits from message patterns
- How AI usage evolved over time
- Quality patterns in AI-assisted vs manual code
- What this reveals about human-AI collaboration
- Lessons for improving AI-assisted development

Title: "AI Collaboration Analysis — {proj['name']}" """,

        "development-rhythm-analysis.md": f"""Generate a development rhythm analysis for "{proj['name']}".

Project context:
{build_context(proj)}

Write a markdown analysis of the development rhythm:
- Work patterns (time of day, day of week)
- Velocity patterns (sprints vs steady, bursts vs gaps)
- How the rhythm changed across eras
- What the commit frequency reveals about development style
- Comparison to typical development patterns

Title: "Development Rhythm Analysis — {proj['name']}" """,

        "technical-decisions-log.md": f"""Generate a technical decisions log for "{proj['name']}".

Project context:
{build_context(proj)}

Write a markdown log of key technical decisions visible in the commit history:
- Architecture choices and when they were made
- Technology adoptions and transitions
- Refactoring decisions
- What was added, removed, or changed
- Decision quality in hindsight

Title: "Technical Decisions Log — {proj['name']}" """,

        "era-deep-dive.md": f"""Generate an era deep-dive for "{proj['name']}".

Project context:
{build_context(proj)}

Write a markdown deep-dive into each era:
- For each era, provide: dates, commit count, key events, themes
- What distinguished each era from the others
- Transition points between eras
- What triggered era changes
- Overall narrative arc

Title: "Era Deep-Dive — {proj['name']}" """,
    }

    for filename, prompt in missing.items():
        target = content_dir / filename
        if target.exists():
            continue

        content = llm_generate(prompt, max_tokens=2500)
        if not content.startswith("ERROR:"):
            content = re.sub(r'<think[^>]*>.*?</think\s*>', '', content, flags=re.DOTALL).strip()
            target.write_text(content, encoding="utf-8")
            count += 1
            print(f"    + {target.name}")
            time.sleep(0.5)

    return count


def ensure_video_files(proj: dict) -> int:
    """Generate missing video content files."""
    count = 0
    video_dir = ROOT / "projects" / proj["name"] / "deliverables" / "video"
    video_dir.mkdir(parents=True, exist_ok=True)

    target = video_dir / "video-script-outline.md"
    if not target.exists():
        prompt = f"""Generate a video script outline for "{proj['name']}".

Project context:
{build_context(proj)}

Write a markdown video script outline:
- Opening hook (30 seconds)
- 3-5 main sections covering the project's story
- Key visuals to show (charts, timelines, code)
- Talking points for each section
- Closing with call to action

Keep it practical for a 5-8 minute video."""

        content = llm_generate(prompt, max_tokens=1500)
        if not content.startswith("ERROR:"):
            content = re.sub(r'<think[^>]*>.*?</think\s*>', '', content, flags=re.DOTALL).strip()
            target.write_text(content, encoding="utf-8")
            count += 1
            print(f"    + {target.name}")
            time.sleep(0.5)

    return count


def generate_for_project(project_name: str) -> None:
    """Generate all missing deliverables for a project."""
    print(f"\n{'='*60}")
    print(f"Generating deliverables for {project_name}")
    print(f"{'='*60}")

    proj = load_project_data(project_name)
    if "eras" not in proj:
        print(f"  SKIP: no era data found for {project_name}")
        return

    total = 0
    total += ensure_analysis_md(proj)
    total += ensure_report_files(proj)
    total += ensure_strategy_files(proj)
    total += ensure_planning_files(proj)
    total += ensure_learning_files(proj)
    total += ensure_content_files(proj)
    total += ensure_video_files(proj)

    print(f"\n  Generated {total} new files for {project_name}")


def main():
    if len(sys.argv) < 2:
        print("Usage: generate_missing_deliverables.py <project_name> | --all")
        sys.exit(1)

    if sys.argv[1] == "--all":
        for proj_name in ["Achiote", "DECLuTTER-AI", "DialectOS", "Epoch", "Fugax", "mcp-video", "openglaze"]:
            generate_for_project(proj_name)
    else:
        generate_for_project(sys.argv[1])

    print("\nDone.")


if __name__ == "__main__":
    main()
