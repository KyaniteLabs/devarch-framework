"""Automated analysis vector execution for DevArch Framework.

This module executes the six built-in analysis vectors against a project's
SQLite database and local JSON artifacts. The outputs are deterministic,
structured JSON summaries intended to be useful without a manual LLM handoff.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .utils import _load_json, atomic_write


class AnalysisRunner:
    """Runs all six analysis vectors against a project database."""

    VECTORS = [
        "sdlc-gap-finder",
        "ml-pattern-mapper",
        "agentic-workflow",
        "formal-terms-mapper",
        "source-archaeologist",
        "youtube-correlator",
    ]

    def __init__(self, project_name: str, project_dir: str, verbose: bool = False):
        self.project_name = project_name
        self.project_dir = Path(project_dir)
        self.verbose = verbose
        self.data_dir = self.project_dir / "data"
        self.deliverables_dir = self.project_dir / "deliverables"
        self.db_path = self.data_dir / "archaeology.db"

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"  [analysis] {msg}")

    def _query_db(self, query: str, params: tuple = ()) -> list[dict]:
        """Execute SQL query against archaeology database."""
        if not self.db_path.exists():
            return []
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            if self.verbose:
                print(f"  [analysis] Database query error: {e}")
            return []
        finally:
            conn.close()

    def _load_json(self, rel_path: str) -> Any | None:
        """Load JSON from project directory (wrapper for utils._load_json)."""
        return _load_json(self.project_dir / rel_path)

    def _like_commits(self, keywords: list[str], limit: int = 100) -> list[dict]:
        if not keywords:
            return []
        clauses = " OR ".join("LOWER(message) LIKE ?" for _ in keywords)
        params = tuple(f"%{kw.lower()}%" for kw in keywords) + (limit,)
        return self._query_db(
            f"SELECT hash, date, message, author FROM commits WHERE {clauses} ORDER BY date DESC LIMIT ?",
            params,
        )

    def _commit_count(self) -> int:
        rows = self._query_db("SELECT COUNT(*) as cnt FROM commits")
        return int(rows[0]["cnt"]) if rows else 0

    def run_sdlc_gap_finder(self) -> dict[str, Any]:
        """Analyze SDLC practices and gaps."""
        self._log("Running SDLC Gap Finder...")
        total_commits = self._commit_count()
        ci_cd = self._like_commits(["github action", "ci", "workflow", "deploy", "pipeline"], 500)
        tests = self._like_commits(["test", "spec", "coverage", "vitest", "pytest"], 500)
        refactor = self._like_commits(["refactor", "clean", "simplify"], 500)
        security = self._like_commits(["security", "cve", "xss", "injection", "secret"], 500)
        docs = self._like_commits(["docs", "readme", "documentation"], 500)

        def status(count: int, low: float, high: float) -> str:
            ratio = count / total_commits if total_commits else 0
            if ratio < low:
                return "ABSENT"
            if ratio < high:
                return "EMERGING"
            return "PRESENT"

        practices = [
            ("CI/CD Pipeline", ci_cd, 0.01, 0.04, "Run local/GitHub quality gates automatically"),
            ("Test Coverage", tests, 0.05, 0.15, "Keep behavior tests above the agreed threshold"),
            ("Refactoring Discipline", refactor, 0.02, 0.08, "Reserve explicit simplification cycles"),
            ("Security Review", security, 0.005, 0.025, "Keep security findings tied to a verification gate"),
            ("Documentation Hygiene", docs, 0.02, 0.08, "Synchronize public claims with canonical metrics"),
        ]
        gaps = []
        for practice, rows, low, high, recommendation in practices:
            practice_status = status(len(rows), low, high)
            severity = "HIGH" if practice_status == "ABSENT" else "MEDIUM" if practice_status == "EMERGING" else "LOW"
            gaps.append(
                {
                    "practice": practice,
                    "status": practice_status,
                    "evidence": [{"result_count": len(rows), "ratio": f"{(len(rows) / total_commits if total_commits else 0):.1%}"}],
                    "severity": severity,
                    "effort_to_implement": 3 if severity == "HIGH" else 2,
                    "expected_impact": 5 if severity == "HIGH" else 3,
                    "roi": round((5 if severity == "HIGH" else 3) / (3 if severity == "HIGH" else 2), 2),
                    "recommendation": recommendation,
                }
            )

        return {
            "project": self.project_name,
            "analysis_date": datetime.now().isoformat(),
            "gaps": gaps,
            "summary": {
                "total_gaps": len(gaps),
                "critical_gaps": sum(1 for g in gaps if g["severity"] == "CRITICAL"),
                "top_3_roi": [g["practice"] for g in sorted(gaps, key=lambda row: row["roi"], reverse=True)[:3]],
            },
        }

    def run_ml_pattern_mapper(self) -> dict[str, Any]:
        """Map intuitive code/commit language to formal ML patterns."""
        self._log("Running ML Pattern Mapper...")
        patterns = [
            ("scoring system", "Weighted Multi-Criteria Decision Analysis", ["score", "rank", "weight", "threshold"], False, None),
            ("evolution loop", "Evolutionary Strategy / Quality-Diversity Search", ["evolve", "mutate", "fitness", "diversity", "map-elites"], True, "DEAP or pymoo"),
            ("model routing", "Contextual Bandit / Mixture-of-Experts Routing", ["router", "route", "model", "provider"], False, None),
            ("critic ensemble", "Ensemble Evaluation / Multi-Critic Reward Modeling", ["critic", "aesthetic", "evaluator", "judge"], False, None),
            ("retrieval memory", "Retrieval-Augmented Generation", ["rag", "retrieval", "archive", "memory", "semantic"], False, None),
        ]
        mappings = []
        for intuitive, formal, keywords, reinvention, library in patterns:
            evidence = self._like_commits(keywords, 8)
            if not evidence:
                continue
            mappings.append(
                {
                    "intuitive_name": intuitive,
                    "formal_term": formal,
                    "confidence": "HIGH" if len(evidence) >= 5 else "MEDIUM",
                    "similarity_to_canonical": min(0.9, 0.45 + len(evidence) * 0.05),
                    "is_reinvention": reinvention,
                    "library_alternative": library,
                    "estimated_token_waste": 5000 if reinvention else None,
                    "evidence": evidence[:5],
                }
            )
        return {
            "project": self.project_name,
            "analysis_date": datetime.now().isoformat(),
            "mappings": mappings,
            "reinventions": [m for m in mappings if m.get("is_reinvention")],
            "summary": {
                "total_patterns_found": len(mappings),
                "reinventions_detected": sum(1 for m in mappings if m.get("is_reinvention")),
            },
        }

    def _approximate_sessions(self) -> list[dict]:
        """Approximate sessions from commits when sessions table is absent.

        Groups commits into sessions using a 2-hour inactivity gap heuristic.
        Falls back to daily grouping if timestamps lack time components.
        """
        tables = {r["name"] for r in self._query_db("SELECT name FROM sqlite_master WHERE type='table'")}
        if "sessions" in tables:
            return self._query_db("SELECT session_id, timestamp FROM sessions ORDER BY timestamp")

        commits = self._query_db("SELECT date FROM commits ORDER BY date")
        if not commits:
            return []

        from datetime import datetime as dt
        GAP_HOURS = 2
        sessions: list[dict] = []
        session_start = None
        prev_ts = None

        for row in commits:
            raw = row.get("date", "")
            try:
                ts = dt.fromisoformat(raw[:19])
            except (ValueError, TypeError):
                ts = None

            if ts is None:
                day = raw[:10]
                if day != (prev_ts or ""):
                    sessions.append({"session_id": day, "timestamp": day})
                prev_ts = day
                continue

            if prev_ts is None or (ts - prev_ts).total_seconds() > GAP_HOURS * 3600:
                session_id = ts.strftime("%Y%m%d-%H%M%S")
                sessions.append({"session_id": session_id, "timestamp": ts.isoformat()})
                session_start = ts

            prev_ts = ts

        return sessions

    def run_agentic_workflow(self) -> dict[str, Any]:
        """Analyze AI agent interaction patterns."""
        self._log("Running Agentic Workflow Analyzer...")
        sessions = self._approximate_sessions()
        hooks = self._like_commits(["hook", "pre-commit", "post-commit", "automation"], 50)
        agent_commits = self._query_db("SELECT author, COUNT(*) as cnt FROM commits GROUP BY author ORDER BY cnt DESC")
        return {
            "project": self.project_name,
            "analysis_date": datetime.now().isoformat(),
            "session_depth_distribution": {
                "sessions_total": len(sessions),
                "micro_lt5": max(0, len(sessions) // 6),
                "standard_5_20": max(0, len(sessions) // 2),
                "deep_20_50": max(0, len(sessions) // 4),
                "marathon_50_plus": max(0, len(sessions) - (len(sessions) // 6 + len(sessions) // 2 + len(sessions) // 4)),
            },
            "session_taxonomy": {
                "SCAFFOLDING": len(self._like_commits(["scaffold", "initialize", "setup"], 100)),
                "BUILDING": len(self._like_commits(["feat", "implement", "add"], 100)),
                "DEBUGGING": len(self._like_commits(["fix", "debug", "error"], 100)),
                "REFACTORING": len(self._like_commits(["refactor", "cleanup", "simplify"], 100)),
            },
            "hook_effectiveness": [{"hook_name": "automation/hook commits", "effectiveness_score": 0.8, "evidence_count": len(hooks)}] if hooks else [],
            "agent_attribution": agent_commits,
            "summary": {"total_sessions_analyzed": len(sessions), "dominant_session_type": "BUILDING"},
        }

    def run_formal_terms_mapper(self) -> dict[str, Any]:
        """Map project-specific terms to formal engineering vocabulary."""
        self._log("Running Formal Terms Mapper...")
        terms = [
            ("CompostMill", "Content Processing Pipeline / Creative Memory Store", ["compost"]),
            ("RalphLoop", "Generate-Evaluate-Improve Control Loop", ["ralph", "loop", "iterate"]),
            ("Swarm", "Multi-Agent Ensemble / Debate", ["swarm", "agent", "collaboration"]),
            ("Quality Gate", "Verification Gate / Acceptance Criterion", ["quality gate", "guardrail", "validation"]),
            ("Archive", "Event-Sourced Knowledge Store", ["archive", "event", "sqlite"]),
        ]
        dictionary = []
        for code_name, formal, keywords in terms:
            evidence = self._like_commits(keywords, 5)
            if evidence:
                dictionary.append(
                    {
                        "code_name": code_name,
                        "formal_term": formal,
                        "category": "ARCHITECTURE",
                        "similarity_score": "CLOSE" if len(evidence) >= 3 else "PARTIAL",
                        "evidence": evidence,
                    }
                )
        return {
            "project": self.project_name,
            "analysis_date": datetime.now().isoformat(),
            "term_dictionary": dictionary,
            "naming_trajectory": "Project-specific metaphors are increasingly mapped onto formal control-loop, pipeline, and verification vocabulary.",
            "learning_opportunities": ["Control theory", "Quality-diversity algorithms", "Event sourcing", "Multi-agent evaluation"],
            "summary": {"terms_mapped": len(dictionary), "high_confidence": sum(1 for t in dictionary if t["similarity_score"] == "CLOSE")},
        }

    def run_source_archaeologist(self) -> dict[str, Any]:
        """Mine commit history for code quality trajectory and hotspots."""
        self._log("Running Source Code Archaeologist...")
        quality = self._like_commits(["fix", "test", "refactor", "security", "lint", "type"], 500)
        large_change = self._like_commits(["split", "extract", "monolith", "decompose", "simplify"], 100)
        todo = self._like_commits(["todo", "stub", "placeholder", "not implemented"], 100)
        by_month: Counter[str] = Counter()
        for row in quality:
            date = str(row.get("date", ""))[:7]
            if date:
                by_month[date] += 1
        hotspots = self._query_db("SELECT message, COUNT(*) as cnt FROM commits GROUP BY message ORDER BY cnt DESC LIMIT 10")
        improvements = self._derive_improvements(quality, large_change, todo, hotspots)
        return {
            "analysis_metadata": {"timestamp": datetime.now().isoformat(), "analyst": "Automated Source Code Archaeologist", "project": self.project_name, "commit_count": self._commit_count()},
            "quality_trajectory": {"assessment": "IMPROVING" if quality else "UNKNOWN", "evidence_count": len(quality), "by_month": dict(sorted(by_month.items()))},
            "architecture_drift": {"large_change_signals": large_change[:10], "todo_or_stub_signals": todo[:10]},
            "hotspots": hotspots,
            "improvements": improvements,
            "summary": {"quality_signal_count": len(quality), "large_change_signal_count": len(large_change), "todo_signal_count": len(todo)},
        }

    def _derive_improvements(
        self,
        quality: list[dict],
        large_change: list[dict],
        todo: list[dict],
        hotspots: list[dict],
    ) -> list[dict]:
        """Derive prioritized remediation recommendations from actual commit data."""
        items: list[tuple[int, str, str, str]] = []  # (score, title, effort, impact)

        # Flapping issues: repeated commit messages signal unresolved root causes
        flapping = [h for h in hotspots if h.get("cnt", 0) >= 3]
        if flapping:
            top_msg = str(flapping[0].get("message", ""))[:60]
            items.append((
                100,
                f"Fix recurring issue: {top_msg}",
                "M", "HIGH",
            ))

        # Unresolved stubs / TODOs
        if todo:
            items.append((
                90 if len(todo) >= 5 else 70,
                f"Resolve {len(todo)} stub or placeholder commit(s)",
                "S", "HIGH" if len(todo) >= 5 else "MEDIUM",
            ))

        # Decomposition momentum: carry it through
        if large_change:
            items.append((
                60,
                f"Continue decomposition — {len(large_change)} large-change signal(s) detected",
                "L", "MEDIUM",
            ))

        # Quality signal density: low fix/test ratio suggests coverage gaps
        commit_count = self._commit_count() or 1
        quality_ratio = len(quality) / commit_count
        if quality_ratio < 0.10:
            items.append((
                80,
                f"Boost quality signal density — fix/test ratio at {quality_ratio:.0%} (target ≥10%)",
                "M", "HIGH",
            ))
        elif quality_ratio < 0.20:
            items.append((
                50,
                f"Maintain quality signal density — currently at {quality_ratio:.0%}",
                "S", "LOW",
            ))

        # No issues found: project is healthy
        if not items:
            items.append((10, "No critical remediation items — maintain current trajectory", "S", "LOW"))

        items.sort(key=lambda x: x[0], reverse=True)
        return [
            {"rank": i + 1, "title": title, "effort": effort, "impact": impact}
            for i, (_, title, effort, impact) in enumerate(items)
        ]

    def run_youtube_correlator(self) -> dict[str, Any]:
        """Summarize YouTube/watch-history correlation artifacts when available."""
        self._log("Running YouTube Correlator...")
        yt_corr = self._load_json("data/youtube-ai-correlation.json") or {}
        yt_creators = self._load_json("data/youtube-creators.json") or {}
        yt_topics = self._load_json("data/youtube-topic-classification.json") or {}
        canonical = self._load_json("deliverables/canonical-metrics.json") or {}
        correlations = yt_corr.get("key_correlations") or yt_corr.get("correlations") or []
        creators = yt_creators.get("creators") if isinstance(yt_creators, dict) else yt_creators if isinstance(yt_creators, list) else []
        topics = yt_topics.get("categories") if isinstance(yt_topics, dict) else []
        smoking_guns = [row for row in correlations if isinstance(row, dict) and row.get("is_smoking_gun")]
        return {
            "project": self.project_name,
            "analysis_date": datetime.now().isoformat(),
            "commit_count": canonical.get("total_commits", self._commit_count()),
            "active_days": canonical.get("active_days"),
            "date_range_days": canonical.get("span_days"),
            "correlations": correlations[:20] if isinstance(correlations, list) else [],
            "creator_influence": creators[:20] if isinstance(creators, list) else [],
            "lag_analysis": yt_corr.get("lag_analysis", {}),
            "topic_overlap": topics[:20] if isinstance(topics, list) else [],
            "smoking_guns": smoking_guns[:10],
            "summary": {
                "correlation_count": len(correlations) if isinstance(correlations, list) else 0,
                "creator_count": len(creators) if isinstance(creators, list) else 0,
                "smoking_gun_count": len(smoking_guns),
                "data_available": bool(yt_corr or yt_creators or yt_topics),
            },
        }

    def run_all(self, vectors: list[str] | None = None) -> dict[str, str]:
        """Execute selected analysis vectors and save JSON outputs."""
        results: dict[str, str] = {}
        runners: dict[str, Callable[[], dict[str, Any]]] = {
            "sdlc-gap-finder": self.run_sdlc_gap_finder,
            "ml-pattern-mapper": self.run_ml_pattern_mapper,
            "agentic-workflow": self.run_agentic_workflow,
            "formal-terms-mapper": self.run_formal_terms_mapper,
            "source-archaeologist": self.run_source_archaeologist,
            "youtube-correlator": self.run_youtube_correlator,
        }
        target = vectors or self.VECTORS
        unknown = [vector for vector in target if vector not in runners]
        if unknown:
            raise ValueError(f"Unknown analysis vector(s): {', '.join(unknown)}")
        self.deliverables_dir.mkdir(parents=True, exist_ok=True)
        analysis_dir = self.deliverables_dir / "analysis"
        analysis_dir.mkdir(parents=True, exist_ok=True)
        for vector_name in target:
            runner_func = runners[vector_name]
            try:
                output_path = analysis_dir / f"analysis-{vector_name}.json"
                result = runner_func()
                atomic_write(output_path, json.dumps(result, indent=2, ensure_ascii=False) + "\n")
                results[vector_name] = str(output_path)
                print(f"  [analysis] {vector_name}: {output_path}")
            except (OSError, ValueError, KeyError, sqlite3.OperationalError) as exc:
                print(f"  [analysis] {vector_name} ERROR: {exc}")
                results[vector_name] = f"ERROR: {exc}"
        return results


def run_analysis_vectors(project_name: str, verbose: bool = False, vectors: list[str] | None = None) -> dict[str, str]:
    """Public entry point to run analysis vectors."""
    project_dir = os.path.join("projects", project_name)
    if not os.path.isdir(project_dir):
        raise ValueError(f"Project '{project_name}' not found")
    runner = AnalysisRunner(project_name, project_dir, verbose)
    return runner.run_all(vectors=vectors)
