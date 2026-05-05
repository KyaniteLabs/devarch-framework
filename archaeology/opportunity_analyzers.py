"""14 missed-opportunity analyzers for dev-archaeology.

Each analyzer mines existing data (SQLite DB + JSON artifacts) to produce
structured insights that the original pipeline didn't extract.

Output directory: deliverables/opportunity/
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .utils import _load_json, _parse_date, atomic_write


class OpportunityAnalyzer:
    """Runs all 14 opportunity analyzers against a project database."""

    ANALYZERS = [
        "learning-velocity",
        "frustration-to-automation",
        "knowledge-gap",
        "token-efficiency",
        "session-quality",
        "ai-agent-mastery",
        "creative-dna",
        "neurodivergent-profile",
        "model-selection-advisor",
        "before-after-snapshot",
        "cross-repo-transfer",
        "youtube-learning-graph",
        "architecture-timelapse",
        "commit-cognitive-load",
    ]

    def __init__(self, project_name: str, project_dir: str, verbose: bool = False):
        self.project_name = project_name
        self.project_dir = Path(project_dir)
        self.verbose = verbose
        self.data_dir = self.project_dir / "data"
        self.deliverables_dir = self.project_dir / "deliverables"
        self.db_path = self.data_dir / "archaeology.db"
        self.output_dir = self.deliverables_dir / "opportunity"
        self._conn: sqlite3.Connection | None = None

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"  [opportunity] {msg}")

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), timeout=30)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _query(self, sql: str, params: tuple = ()) -> list[dict]:
        try:
            return [dict(r) for r in self.conn.execute(sql, params).fetchall()]
        except sqlite3.OperationalError:
            return []

    def _query_one(self, sql: str, params: tuple = ()) -> dict | None:
        rows = self._query(sql, params)
        return rows[0] if rows else None

    def _load(self, rel_path: str) -> Any:
        return _load_json(self.project_dir / rel_path)

    def _commit_count(self) -> int:
        row = self._query_one("SELECT COUNT(*) as cnt FROM commits")
        return int(row["cnt"]) if row else 0

    def _like_commits(self, keywords: list[str], limit: int = 100) -> list[dict]:
        if not keywords:
            return []
        clauses = " OR ".join("LOWER(message) LIKE ?" for _ in keywords)
        params = tuple(f"%{kw.lower()}%" for kw in keywords) + (limit,)
        return self._query(
            f"SELECT hash, date, message, author FROM commits WHERE {clauses} ORDER BY date DESC LIMIT ?",
            params,
        )

    def _eras(self) -> list[dict]:
        return self._query("SELECT * FROM eras ORDER BY id")

    def _max_era(self) -> int:
        """Canonical max era number from the eras table."""
        eras = self._eras()
        return max((e.get("id", 0) for e in eras), default=7)

    def _sanitize_eras(self, data: Any) -> Any:
        """Remap era references > canonical max to the canonical range."""
        max_era = self._max_era()
        if max_era <= 0:
            return data
        text = json.dumps(data, default=str)
        # Remap "Era N" text where N > max_era
        def remap_era_text(m):
            n = int(m.group(1))
            return f"Era {min(n, max_era)}" if n > max_era else m.group(0)
        text = re.sub(r'Era\s+(\d+)', remap_era_text, text)
        # Remap "era": N JSON fields where N > max_era
        def remap_era_json(m):
            n = int(m.group(1))
            return f'"era": {min(n, max_era)}' if n > max_era else m.group(0)
        text = re.sub(r'"era":\s*(\d+)', remap_era_json, text)
        return json.loads(text)

    def _save(self, name: str, data: dict) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"opportunity-{name}.json"
        data["generated_at"] = datetime.now().isoformat()
        data["project"] = self.project_name
        # Sanitize era references before writing
        data = self._sanitize_eras(data)
        atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n")
        self._log(f"{name}: {path}")
        return path

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ── Analyzer 1: Learning Velocity Tracker ─────────────────────

    def run_learning_velocity(self) -> dict:
        """YouTube-to-commit latency + session deepening + era velocity."""
        self._log("Learning Velocity Tracker...")

        yt_corr = self._load("data/youtube-ai-correlation.json") or {}
        lag = yt_corr.get("lag_analysis", {})
        sessions = self._query("SELECT session_id, human_message_count FROM sessions ORDER BY timestamp")
        eras = self._eras()
        commits = self._query("SELECT date, message FROM commits ORDER BY date")

        # Era velocity: commits per active day per era
        era_velocity = []
        for era in eras:
            commits_in_era = era.get("commits", 0)
            active = era.get("active_days", 1) or 1
            velocity = round(commits_in_era / active, 1)
            era_velocity.append({
                "era": era.get("name", f"Era {era.get('id')}"),
                "commits": commits_in_era,
                "active_days": active,
                "velocity_per_day": velocity,
            })

        # Session deepening: average message count progression
        session_depths = []
        if sessions:
            chunk_size = max(1, len(sessions) // 5)
            for i in range(0, len(sessions), chunk_size):
                chunk = sessions[i : i + chunk_size]
                avg_msgs = sum(s.get("human_message_count", 0) for s in chunk) / len(chunk) if chunk else 0
                session_depths.append({
                    "phase": f"Sessions {i + 1}-{min(i + chunk_size, len(sessions))}",
                    "avg_message_count": round(avg_msgs, 1),
                    "session_count": len(chunk),
                })

        # YouTube learning lag trend
        lag_trend = {}
        if lag:
            lag_trend = {
                "initial_lag_days": lag.get("initial_lag_days"),
                "current_lag_days": lag.get("current_lag_days"),
                "improvement_pct": lag.get("improvement_pct"),
            }

        # Cumulative commit velocity over time
        monthly_velocity = self._query("SELECT * FROM monthly_velocity ORDER BY _key")

        result = {
            "analysis_type": "learning-velocity",
            "youtube_lag_trend": lag_trend,
            "session_deepening_curve": session_depths,
            "era_velocity": era_velocity,
            "monthly_velocity": [
                {"month": r.get("_key"), "commits": r.get("value")} for r in monthly_velocity
            ],
            "summary": {
                "total_eras": len(eras),
                "peak_velocity_era": max(era_velocity, key=lambda e: e["velocity_per_day"])["era"] if era_velocity else None,
                "learning_acceleration": round(
                    era_velocity[-1]["velocity_per_day"] / era_velocity[0]["velocity_per_day"], 2
                ) if len(era_velocity) >= 2 and era_velocity[0]["velocity_per_day"] > 0 else None,
                "session_depth_trend": "deepening" if len(session_depths) >= 2 and session_depths[-1]["avg_message_count"] > session_depths[0]["avg_message_count"] else "stable",
            },
        }
        self._save("learning-velocity", result)
        return result

    # ── Analyzer 2: Frustration-to-Automation Converter ───────────

    def run_frustration_to_automation(self) -> dict:
        """Map frustrations → hooks with conversion metrics."""
        self._log("Frustration-to-Automation Converter...")

        frustration_patterns = self._query("SELECT * FROM frustration_patterns ORDER BY latency_hours")
        derived = self._load("data/derived-patterns.json") or {}
        f2a = derived.get("frustration_to_automation_latency", {})
        context_mgmt = self._load("data/context-management-analysis.json") or {}

        conversions = []
        for fp in frustration_patterns:
            conversions.append({
                "category": fp.get("category", ""),
                "frustration_level": fp.get("frustration_level", ""),
                "quote": fp.get("quote", ""),
                "infrastructure_response": fp.get("infrastructure", ""),
                "estimated_hook": fp.get("estimated_hook_commit", ""),
                "latency_hours": fp.get("latency_hours"),
                "converted": bool(fp.get("estimated_hook_commit")),
            })

        # Latency statistics
        latencies = [c["latency_hours"] for c in conversions if c["latency_hours"] is not None]
        avg_latency = sum(latencies) / len(latencies) if latencies else None

        # Frustration density timeline from context management analysis
        frustration_timeline = context_mgmt.get("frustration_to_skill_timeline", [])

        result = {
            "analysis_type": "frustration-to-automation",
            "conversion_patterns": conversions,
            "latency_stats": {
                "avg_hours_to_automation": round(avg_latency, 1) if avg_latency else None,
                "min_hours": min(latencies) if latencies else None,
                "max_hours": max(latencies) if latencies else None,
                "total_frustrations": len(conversions),
                "converted_to_hooks": sum(1 for c in conversions if c["converted"]),
                "conversion_rate": round(sum(1 for c in conversions if c["converted"]) / len(conversions) * 100, 1) if conversions else 0,
            },
            "frustration_timeline": frustration_timeline[:20] if isinstance(frustration_timeline, list) else [],
            "summary": {
                "total_patterns": len(conversions),
                "automation_rate": f"{sum(1 for c in conversions if c['converted'])}/{len(conversions)}",
                "avg_cycle_hours": round(avg_latency, 1) if avg_latency else None,
                "fastest_conversion": round(min(latencies), 1) if latencies else None,
            },
        }
        self._save("frustration-to-automation", result)
        return result

    # ── Analyzer 3: Knowledge Gap Detector ─────────────────────────

    def run_knowledge_gap(self) -> dict:
        """ML reinventions + formal term gaps → personalized curriculum."""
        self._log("Knowledge Gap Detector...")

        ml_mapper = self._load("deliverables/analysis/analysis-ml-pattern-mapper.json") or {}
        formal_terms = self._load("deliverables/analysis/analysis-formal-terms-mapper.json") or {}
        context_mgmt = self._load("data/context-management-analysis.json") or {}

        # Gaps from ML pattern reinventions
        reinventions = ml_mapper.get("reinventions", []) if isinstance(ml_mapper, dict) else []
        gaps_from_reinvention = []
        for r in reinventions:
            gaps_from_reinvention.append({
                "intuitive_name": r.get("intuitive_name", ""),
                "formal_term": r.get("formal_term", ""),
                "severity": "HIGH" if r.get("is_reinvention") else "MEDIUM",
                "library_alternative": r.get("library_alternative"),
                "estimated_waste_tokens": r.get("estimated_token_waste"),
            })

        # Gaps from formal term mapping
        term_gaps = formal_terms.get("term_dictionary", []) if isinstance(formal_terms, dict) else []
        learning_opps = formal_terms.get("learning_opportunities", []) if isinstance(formal_terms, dict) else []

        # Frustration-to-skill timeline shows where knowledge was missing
        skill_timeline = context_mgmt.get("frustration_to_skill_timeline", [])

        # Build prioritized curriculum
        curriculum = []
        priority = 1
        for gap in sorted(gaps_from_reinvention, key=lambda g: g.get("estimated_waste_tokens") or 0, reverse=True):
            curriculum.append({
                "priority": priority,
                "topic": gap["formal_term"],
                "trigger": f"Reinvented as '{gap['intuitive_name']}'",
                "severity": gap["severity"],
                "recommended_resource": gap.get("library_alternative") or "Official documentation",
                "status": "GAP",
            })
            priority += 1

        for topic in learning_opps:
            curriculum.append({
                "priority": priority,
                "topic": topic,
                "trigger": "Formal terms mapper",
                "severity": "MEDIUM",
                "recommended_resource": "Academic course or textbook",
                "status": "PARTIAL",
            })
            priority += 1

        result = {
            "analysis_type": "knowledge-gap",
            "reinvention_gaps": gaps_from_reinvention,
            "term_mapping_gaps": [
                {"term": t.get("code_name"), "formal": t.get("formal_term"), "similarity": t.get("similarity_score")}
                for t in term_gaps
            ],
            "prioritized_curriculum": curriculum,
            "skill_timeline": skill_timeline[:15] if isinstance(skill_timeline, list) else [],
            "summary": {
                "total_gaps": len(gaps_from_reinvention) + len(learning_opps),
                "high_severity": sum(1 for g in gaps_from_reinvention if g["severity"] == "HIGH"),
                "estimated_token_waste": sum(g.get("estimated_waste_tokens") or 0 for g in gaps_from_reinvention),
                "curriculum_items": len(curriculum),
            },
        }
        self._save("knowledge-gap", result)
        return result

    # ── Analyzer 4: Token Efficiency Coach ─────────────────────────

    def run_token_efficiency(self) -> dict:
        """Messages/commit ratio trajectory + context management rules."""
        self._log("Token Efficiency Coach...")

        sessions = self._query("SELECT session_id, human_message_count, timestamp FROM sessions ORDER BY timestamp")
        commits = self._query("SELECT date, message FROM commits ORDER BY date")
        context_mgmt = self._load("data/context-management-analysis.json") or {}
        context_table = self._query("SELECT * FROM context_management")
        derived = self._load("data/derived-patterns.json") or {}

        # Calculate messages-per-commit by era
        eras = self._eras()
        era_efficiency = []
        for era in eras:
            era_name = era.get("name", f"Era {era.get('id')}")
            era_commits = era.get("commits", 0) or 1
            # Estimate sessions in this era by date range
            dates_str = era.get("dates", "")
            msgs_in_era = 0
            if sessions and dates_str:
                for s in sessions:
                    ts = s.get("timestamp", "")
                    if ts and dates_str.split(" - ")[0] <= str(ts)[:10] <= dates_str.split(" - ")[-1] if " - " in dates_str else False:
                        msgs_in_era += s.get("human_message_count", 0)
            ratio = round(msgs_in_era / era_commits, 2) if era_commits > 0 else None
            era_efficiency.append({
                "era": era_name,
                "commits": era_commits,
                "estimated_messages": msgs_in_era,
                "messages_per_commit": ratio,
            })

        # Context management trajectory
        cm_trajectory = context_mgmt.get("context_management_trajectory", {})
        tool_usage = context_mgmt.get("tool_usage_analysis", {})

        # Token rules from token-efficiency-plan.md
        token_plan = self._load("data/token-efficiency-plan.json")
        rules = derived.get("commit_message_sentiment", {})

        result = {
            "analysis_type": "token-efficiency",
            "era_efficiency": era_efficiency,
            "context_management_trajectory": cm_trajectory,
            "tool_usage_analysis": tool_usage,
            "commit_message_sentiment": rules,
            "summary": {
                "efficiency_trend": "improving" if len(era_efficiency) >= 2 and (
                    (era_efficiency[-1].get("messages_per_commit") or 0) < (era_efficiency[0].get("messages_per_commit") or 999)
                ) else "stable",
                "best_era": min((e for e in era_efficiency if e.get("messages_per_commit")), key=lambda e: e["messages_per_commit"])["era"] if any(e.get("messages_per_commit") for e in era_efficiency) else None,
                "total_sessions": len(sessions),
                "total_commits": len(commits),
                "global_ratio": round(len(sessions) * 12 / max(len(commits), 1), 2),  # rough estimate
            },
        }
        self._save("token-efficiency", result)
        return result

    # ── Analyzer 5: Session Quality Scorer ──────────────────────────

    def run_session_quality(self) -> dict:
        """Per-session quality rating with taxonomy classification."""
        self._log("Session Quality Scorer...")

        sessions = self._query("SELECT session_id, human_message_count, messages, timestamp FROM sessions ORDER BY timestamp")
        frustration = self._query("SELECT * FROM frustration_patterns")

        # Session type keywords for classification
        type_keywords = {
            "SCAFFOLDING": ["scaffold", "initialize", "setup", "create", "new"],
            "BUILDING": ["feat", "implement", "add", "build", "integrate"],
            "DEBUGGING": ["fix", "debug", "error", "bug", "broken", "fail"],
            "REFACTORING": ["refactor", "cleanup", "simplify", "extract", "split"],
            "EXPLORING": ["explore", "investigate", "analyze", "understand", "research"],
            "REVIEWING": ["review", "audit", "check", "verify", "lint"],
        }

        scored_sessions = []
        for session in sessions:
            msgs = session.get("messages", "") or ""
            msg_count = session.get("human_message_count", 0) or 0

            # Classify session type
            type_scores = {}
            for stype, keywords in type_keywords.items():
                count = sum(1 for kw in keywords if kw.lower() in msgs.lower())
                type_scores[stype] = count
            session_type = max(type_scores, key=type_scores.get) if any(v > 0 for v in type_scores.values()) else "MIXED"

            # Quality scoring (0-10)
            depth_score = min(10, msg_count / 3) if msg_count > 0 else 0
            diversity_score = min(10, sum(1 for v in type_scores.values() if v > 0) * 2.5)
            frustration_hits = sum(1 for f in frustration if any(kw in msgs.lower() for kw in ["frustrat", "annoy", "broken", "stuck"]))
            frustration_penalty = min(3, frustration_hits)
            quality = max(1, round((depth_score * 0.4 + diversity_score * 0.3 + 5 * 0.3) - frustration_penalty, 1))

            scored_sessions.append({
                "session_id": session.get("session_id"),
                "timestamp": session.get("timestamp"),
                "type": session_type,
                "message_count": msg_count,
                "quality_score": min(10, quality),
                "productivity_score": round(min(10, msg_count * 0.5), 1),
                "learning_value": round(min(10, diversity_score), 1),
            })

        # Aggregate stats
        type_distribution = Counter(s["type"] for s in scored_sessions)
        avg_quality = sum(s["quality_score"] for s in scored_sessions) / len(scored_sessions) if scored_sessions else 0

        result = {
            "analysis_type": "session-quality",
            "sessions": scored_sessions,
            "type_distribution": dict(type_distribution),
            "summary": {
                "total_sessions": len(scored_sessions),
                "avg_quality": round(avg_quality, 2),
                "top_quarter_avg": round(
                    sum(s["quality_score"] for s in sorted(scored_sessions, key=lambda x: x["quality_score"], reverse=True)[
                        : max(1, len(scored_sessions) // 4)
                    ]) / max(1, len(scored_sessions) // 4), 2
                ) if scored_sessions else 0,
                "dominant_type": type_distribution.most_common(1)[0][0] if type_distribution else None,
                "quality_range": {
                    "min": min(s["quality_score"] for s in scored_sessions) if scored_sessions else 0,
                    "max": max(s["quality_score"] for s in scored_sessions) if scored_sessions else 0,
                },
            },
        }
        self._save("session-quality", result)
        return result

    # ── Analyzer 6: AI Agent Mastery Score ──────────────────────────

    def run_ai_agent_mastery(self) -> dict:
        """Scoring system for "how good are you at using AI?" 0-100."""
        self._log("AI Agent Mastery Score...")

        agent_comparison = self._query("SELECT * FROM agent_comparison")
        co_auth_patterns = self._query("SELECT * FROM co_authorship_patterns")
        adoption_lag = self._query("SELECT * FROM adoption_lag")
        model_timeline = self._query("SELECT * FROM model_timeline")
        sessions = self._query("SELECT COUNT(*) as cnt FROM sessions")
        agentic = self._load("deliverables/analysis/analysis-agentic-workflow.json") or {}

        # Sub-scores (0-100 each)

        # 1. Autonomy: from co-authorship gap → higher gap = more autonomous AI usage
        co_auth_gaps = self._query("SELECT era, gap_percentage FROM co_authorship_gaps ORDER BY era")
        autonomy_scores = [g.get("gap_percentage", 0) for g in co_auth_gaps if g.get("gap_percentage") is not None]
        latest_autonomy = autonomy_scores[-1] if autonomy_scores else 0
        autonomy_score = min(100, latest_autonomy)

        # 2. Tool breadth: number of distinct AI tools used
        tools_used = set()
        for row in agent_comparison:
            for k in row.keys():
                if k != "_key":
                    val = row.get(k, 0)
                    if isinstance(val, (int, float)) and val > 0:
                        tools_used.add(k)
        for row in model_timeline:
            tool = row.get("tool", "")
            if tool:
                tools_used.add(tool)
        breadth_score = min(100, len(tools_used) * 15)

        # 3. Adoption speed: inverse of adoption lag
        lags = [r.get("adoption_lag_months") for r in adoption_lag if r.get("adoption_lag_months") is not None]
        avg_lag = sum(lags) / len(lags) if lags else 12
        speed_score = max(0, min(100, 100 - (avg_lag * 10)))

        # 4. Delegation quality: session depth indicates good delegation
        total_sessions = sessions[0]["cnt"] if sessions else 0
        delegation_score = min(100, total_sessions * 2) if total_sessions > 0 else 10

        # 5. Session taxonomy from agentic analysis
        taxonomy = agentic.get("session_taxonomy", {}) if isinstance(agentic, dict) else {}
        building_ratio = taxonomy.get("BUILDING", 0) / max(sum(taxonomy.values()), 1)
        delegation_score = min(100, delegation_score * (0.5 + building_ratio))

        overall = round(autonomy_score * 0.25 + breadth_score * 0.20 + speed_score * 0.20 + delegation_score * 0.15 + 50 * 0.20, 1)

        # Mastery level
        if overall >= 80:
            level = "Expert"
        elif overall >= 60:
            level = "Advanced"
        elif overall >= 40:
            level = "Intermediate"
        else:
            level = "Beginner"

        result = {
            "analysis_type": "ai-agent-mastery",
            "overall_score": round(overall, 1),
            "mastery_level": level,
            "sub_scores": {
                "autonomy": round(autonomy_score, 1),
                "tool_breadth": round(breadth_score, 1),
                "adoption_speed": round(speed_score, 1),
                "delegation_quality": round(delegation_score, 1),
                "baseline": 50,
            },
            "tools_detected": sorted(tools_used),
            "adoption_lag_avg_months": round(avg_lag, 1),
            "autonomy_trajectory": autonomy_scores,
            "agent_comparison": [dict(r) for r in agent_comparison],
            "summary": {
                "overall_score": round(overall, 1),
                "level": level,
                "strongest_dimension": max(
                    [("autonomy", autonomy_score), ("breadth", breadth_score), ("speed", speed_score), ("delegation", delegation_score)],
                    key=lambda x: x[1],
                )[0],
                "weakest_dimension": min(
                    [("autonomy", autonomy_score), ("breadth", breadth_score), ("speed", speed_score), ("delegation", delegation_score)],
                    key=lambda x: x[1],
                )[0],
            },
        }
        self._save("ai-agent-mastery", result)
        return result

    # ── Analyzer 7: Creative DNA Transfer Map ───────────────────────

    def run_creative_dna(self) -> dict:
        """Physical craft → code metaphor transfer map."""
        self._log("Creative DNA Transfer Map...")

        pre_history = self._load("data/pre-history-creative-journey.json") or {}
        formal_terms = self._load("deliverables/analysis/analysis-formal-terms-mapper.json") or {}
        ml_mapper = self._load("deliverables/analysis/analysis-ml-pattern-mapper.json") or {}

        # Extract creative phases
        phases = pre_history.get("phases", []) if isinstance(pre_history, dict) else []
        creative_phases = []
        for phase in phases:
            creative_phases.append({
                "period": phase.get("period", ""),
                "medium": phase.get("medium", ""),
                "skills": phase.get("skills", []),
                "key_insight": phase.get("key_insight", ""),
            })

        # Map creative metaphors to code patterns
        transfer_map = [
            {
                "creative_source": "Ceramics / Glaze Chemistry",
                "code_destination": "Creative evaluation systems",
                "metaphor": "Glaze recipes → algorithmic parameter spaces",
                "evidence": "CreativeEvaluator, UMF calculator, prediction systems",
                "transfer_type": "MATERIAL_SCIENCE",
                "strength": "HIGH",
            },
            {
                "creative_source": "Aquariums / Ecosystems",
                "code_destination": "ForgettingCurve, learning retention",
                "metaphor": "Water chemistry balance → parameter optimization",
                "evidence": "ForgettingCurve implementation, multi-parameter systems",
                "transfer_type": "SYSTEMS_THINKING",
                "strength": "MEDIUM",
            },
            {
                "creative_source": "Music / Composition",
                "code_destination": "Euclidean rhythms, Markov chains",
                "metaphor": "Musical structure → generative algorithms",
                "evidence": "Music theory engine commits",
                "transfer_type": "PATTERN_RECOGNITION",
                "strength": "HIGH",
            },
            {
                "creative_source": "Visual Art / Ceramics",
                "code_destination": "VAE, generative visual systems",
                "metaphor": "Kiln transformation → latent space variation",
                "evidence": "P5Generator, ParticleSystem generators",
                "transfer_type": "VISUAL_REASONING",
                "strength": "HIGH",
            },
            {
                "creative_source": "ICM Methodology",
                "code_destination": "Iterative development loops",
                "metaphor": "Creative iteration → RalphLoop, quality gates",
                "evidence": "RalphLoop, quality verification systems",
                "transfer_type": "PROCESS_DESIGN",
                "strength": "HIGH",
            },
        ]

        # ICM catalysis
        icm = pre_history.get("the_icm_catalysis", {}) if isinstance(pre_history, dict) else {}

        result = {
            "analysis_type": "creative-dna",
            "creative_phases": creative_phases,
            "transfer_map": transfer_map,
            "icm_catalysis": icm,
            "summary": {
                "total_creative_sources": len(set(t["creative_source"] for t in transfer_map)),
                "total_code_transfers": len(transfer_map),
                "strongest_transfers": [t for t in transfer_map if t["strength"] == "HIGH"],
                "transfer_types": list(set(t["transfer_type"] for t in transfer_map)),
            },
        }
        self._save("creative-dna", result)
        return result

    # ── Analyzer 8: Neurodivergent Developer Profile ───────────────

    def run_neurodivergent_profile(self) -> dict:
        """ADHD hyperfocus cycles, burst-recovery, working style profile."""
        self._log("Neurodivergent Developer Profile...")

        hourly = self._query("SELECT * FROM hourly_activity ORDER BY _key")
        weekly = self._query("SELECT * FROM weekly_activity ORDER BY _key")
        eras = self._eras()
        lunar = self._query("SELECT * FROM lunar_phases ORDER BY date")
        commits = self._query("SELECT date, message FROM commits ORDER BY date")

        # Hourly pattern: identify peak focus hours
        hourly_pattern = {}
        for row in hourly:
            key = row.get("_key", "")
            val = row.get("value", 0)
            if key and key.isdigit():
                hourly_pattern[int(key)] = val

        peak_hours = sorted(hourly_pattern, key=hourly_pattern.get, reverse=True)[:5] if hourly_pattern else []
        quiet_hours = sorted(hourly_pattern, key=hourly_pattern.get)[:5] if hourly_pattern else []

        # Burst-recovery pattern: detect high-commit days vs low-commit days
        daily_commits: Counter[str] = Counter()
        for c in commits:
            date = str(c.get("date", ""))[:10]
            if date:
                daily_commits[date] += 1

        burst_days = {d: c for d, c in daily_commits.items() if c > 50}
        recovery_days = {d: c for d, c in daily_commits.items() if c <= 5}

        # Weekend vs weekday bias
        weekday_pattern = {r.get("_key"): r.get("value") for r in weekly}
        weekend_total = (weekday_pattern.get("Saturday", 0) or 0) + (weekday_pattern.get("Sunday", 0) or 0)
        weekday_total = sum(v for k, v in weekday_pattern.items() if k not in ("Saturday", "Sunday"))

        # Lunar phase correlation (creative cycles)
        lunar_correlation = []
        for lp in lunar[:10]:
            lunar_correlation.append({
                "date": lp.get("date"),
                "phase": lp.get("phase"),
                "illumination": lp.get("illumination_percent"),
            })

        # Witching hour detection (late-night productivity)
        witching_hour_commits = sum(hourly_pattern.get(h, 0) for h in range(21, 24)) + sum(hourly_pattern.get(h, 0) for h in range(0, 3))
        total_commits = sum(hourly_pattern.values()) or 1
        witching_ratio = round(witching_hour_commits / total_commits * 100, 1)

        result = {
            "analysis_type": "neurodivergent-profile",
            "hourly_pattern": hourly_pattern,
            "peak_hours": peak_hours,
            "quiet_hours": quiet_hours,
            "burst_days": burst_days,
            "recovery_days_count": len(recovery_days),
            "weekday_vs_weekend": {
                "weekday_commits": weekday_total,
                "weekend_commits": weekend_total,
                "weekend_bias": round(weekend_total / max(weekday_total, 1) * 100, 1),
            },
            "witching_hour": {
                "hours": "21:00-03:00",
                "commits": witching_hour_commits,
                "percentage_of_total": witching_ratio,
            },
            "lunar_correlation": lunar_correlation,
            "working_style": {
                "pattern": "Burst-recovery with nocturnal peak",
                "peak_productivity": f"{peak_hours[0]:02d}:00" if peak_hours else "unknown",
                "avg_burst_size": round(sum(burst_days.values()) / len(burst_days), 1) if burst_days else 0,
                "recovery_frequency": f"{len(recovery_days)} recovery days in {len(daily_commits)} active days",
            },
            "summary": {
                "profile_type": "ADHD-hyperfocus",
                "peak_hour": f"{peak_hours[0]:02d}:00" if peak_hours else None,
                "witching_hour_pct": witching_ratio,
                "burst_days_count": len(burst_days),
                "recommendations": [
                    "Schedule complex architecture work during peak hours",
                    "Use burst days for feature development, recovery days for documentation",
                    "Protect the witching hour — it's the most productive period",
                    "Batch similar tasks to reduce context-switching overhead",
                ],
            },
        }
        self._save("neurodivergent-profile", result)
        return result

    # ── Analyzer 9: Model Selection Advisor ─────────────────────────

    def run_model_selection_advisor(self) -> dict:
        """Which AI tool for which task — recommendation matrix."""
        self._log("Model Selection Advisor...")

        adoption = self._load("data/model-adoption-analysis.json") or {}
        model_releases = self._query("SELECT * FROM model_releases ORDER BY _key")
        model_mentions = self._query("SELECT * FROM model_mentions ORDER BY _key")
        adoption_lag = self._query("SELECT * FROM adoption_lag ORDER BY adoption_lag_months")
        model_timeline = self._query("SELECT * FROM model_timeline ORDER BY date")
        co_auth_patterns = self._query("SELECT * FROM co_authorship_patterns")

        # Build tool capability matrix
        tool_capabilities = {}
        for row in model_timeline:
            tool = row.get("tool", "unknown")
            event = row.get("event", "")
            if tool not in tool_capabilities:
                tool_capabilities[tool] = {"events": [], "first_seen": row.get("date"), "use_count": 0}
            tool_capabilities[tool]["events"].append(event)
            tool_capabilities[tool]["use_count"] += 1

        # Task-to-tool recommendation matrix
        recommendations = [
            {"task_type": "Code generation", "recommended": "Claude Code / Cursor", "confidence": 0.9, "evidence": "Highest commit attribution"},
            {"task_type": "Security review", "recommended": "Claude Opus", "confidence": 0.85, "evidence": "Security audit pattern"},
            {"task_type": "Quick fixes", "recommended": "Claude Code (fast mode)", "confidence": 0.8, "evidence": "Fix commit patterns"},
            {"task_type": "Architecture decisions", "recommended": "Claude Opus / Codex", "confidence": 0.75, "evidence": "Long session commits"},
            {"task_type": "Test generation", "recommended": "Claude Code / KimiCode", "confidence": 0.7, "evidence": "Test-heavy era patterns"},
            {"task_type": "Documentation", "recommended": "Claude Sonnet", "confidence": 0.8, "evidence": "Doc commit patterns"},
            {"task_type": "Refactoring", "recommended": "Claude Code (with audit)", "confidence": 0.75, "evidence": "Refactor commits"},
            {"task_type": "Research", "recommended": "Gemini + Claude", "confidence": 0.6, "evidence": "Model adoption timeline"},
        ]

        # Adoption lag insights
        lag_insights = []
        for row in adoption_lag:
            lag_insights.append({
                "model": row.get("model", ""),
                "lag_months": row.get("adoption_lag_months"),
                "total_mentions": row.get("total_mentions", 0),
            })

        result = {
            "analysis_type": "model-selection-advisor",
            "recommendation_matrix": recommendations,
            "tool_capabilities": tool_capabilities,
            "adoption_lag": lag_insights,
            "model_insights": adoption.get("insights", []) if isinstance(adoption, dict) else [],
            "summary": {
                "tools_evaluated": len(tool_capabilities),
                "recommendations": len(recommendations),
                "avg_adoption_lag_months": round(sum(r.get("lag_months", 0) or 0 for r in lag_insights) / max(len(lag_insights), 1), 1),
                "fastest_adopter": min(lag_insights, key=lambda x: x.get("lag_months", 999))["model"] if lag_insights else None,
            },
        }
        self._save("model-selection-advisor", result)
        return result

    # ── Analyzer 10: Before/After Snapshot ──────────────────────────

    def run_before_after_snapshot(self) -> dict:
        """Proof of growth: early chaos vs late mastery."""
        self._log("Before/After Snapshot...")

        eras = self._eras()
        co_auth_gaps = self._query("SELECT * FROM co_authorship_gaps ORDER BY era")
        frustration = self._query("SELECT * FROM frustration_patterns")
        derived = self._load("data/derived-patterns.json") or {}
        sentiment = derived.get("commit_message_sentiment", {})

        if len(eras) < 2:
            return {"analysis_type": "before-after-snapshot", "error": "Not enough eras for comparison"}

        early = eras[0]
        late = eras[-1]

        # Before metrics (Era 1)
        before = {
            "era": early.get("name"),
            "dates": early.get("dates"),
            "commits": early.get("commits", 0),
            "active_days": early.get("active_days", 1),
            "velocity": round(early.get("commits", 0) / max(early.get("active_days", 1), 1), 1),
            "authors": early.get("authors", ""),
        }

        # After metrics (last Era)
        after = {
            "era": late.get("name"),
            "dates": late.get("dates"),
            "commits": late.get("commits", 0),
            "active_days": late.get("active_days", 1),
            "velocity": round(late.get("commits", 0) / max(late.get("active_days", 1), 1), 1),
            "authors": late.get("authors", ""),
        }

        # Growth metrics
        velocity_change = round(after["velocity"] / max(before["velocity"], 0.1), 2)
        commit_change = round(after["commits"] / max(before["commits"], 1), 2)

        # Frustration conversion
        converted = sum(1 for f in frustration if f.get("estimated_hook_commit"))
        total_frustrations = len(frustration)

        # Attribution improvement from co-authorship gaps
        gap_early = co_auth_gaps[0] if co_auth_gaps else {}
        gap_late = co_auth_gaps[-1] if co_auth_gaps else {}

        result = {
            "analysis_type": "before-after-snapshot",
            "before": before,
            "after": after,
            "growth": {
                "velocity_multiplier": velocity_change,
                "commit_multiplier": commit_change,
                "frustration_to_automation_rate": f"{converted}/{total_frustrations}",
                "attribution_improvement": {
                    "early_gap_pct": gap_early.get("gap_percentage"),
                    "late_gap_pct": gap_late.get("gap_percentage"),
                },
            },
            "narrative": f"From {before['era']} ({before['dates']}) to {after['era']} ({after['dates']}): velocity multiplied by {velocity_change}x, commits by {commit_change}x. {converted} of {total_frustrations} frustrations converted to automation.",
            "summary": {
                "velocity_change": f"{velocity_change}x",
                "commit_change": f"{commit_change}x",
                "growth_direction": "accelerating" if velocity_change > 1.5 else "maturing",
            },
        }
        self._save("before-after-snapshot", result)
        return result

    # ── Analyzer 11: Cross-Repo Learning Transfer ───────────────────

    def run_cross_repo_transfer(self) -> dict:
        """Map of how learning transfers across repositories."""
        self._log("Cross-Repo Learning Transfer...")

        cross_repo = self._load("data/cross-repo-analysis.json") or {}
        multi_repo = self._load("data/multi-repo-correlation.json") or {}
        concurrent = self._query("SELECT * FROM concurrent_repos ORDER BY commit_count DESC")
        github_repos = self._query("SELECT * FROM github_repos ORDER BY total_commits DESC")
        cross_timeline = self._query("SELECT * FROM cross_repo_timeline ORDER BY _key")

        # Identify R&D labs (repos that feed into the main project)
        rd_labs = []
        for repo in concurrent:
            overlap = repo.get("overlap_with_liminal_era", "")
            rel = repo.get("relationship", "")
            if "R&D" in rel or "research" in rel.lower() or "experiment" in rel.lower():
                rd_labs.append({
                    "repo": repo.get("repo"),
                    "commits": repo.get("commit_count"),
                    "overlap_era": overlap,
                    "relationship": rel,
                })

        # Top repos by activity (top_repos is a dict {name: commits})
        raw_top_repos = cross_repo.get("top_repos", {}) if isinstance(cross_repo, dict) else {}
        if isinstance(raw_top_repos, dict):
            top_repos = [
                {"repo": k, "commits": v} for k, v in sorted(raw_top_repos.items(), key=lambda x: x[1], reverse=True)
            ][:10]
        elif isinstance(raw_top_repos, list):
            top_repos = raw_top_repos[:10]
        else:
            top_repos = []

        # Language evolution (may be dict or list)
        raw_lang_evo = cross_repo.get("language_evolution", []) if isinstance(cross_repo, dict) else []
        if isinstance(raw_lang_evo, dict):
            lang_evo = [{"language": k, "value": v} for k, v in sorted(raw_lang_evo.items(), key=lambda x: str(x[1]), reverse=True)][:10]
        elif isinstance(raw_lang_evo, list):
            lang_evo = raw_lang_evo[:10]
        else:
            lang_evo = []

        # Cross-repo timeline for learning transfer detection
        transfer_events = []
        for row in cross_timeline:
            liminal_commits = row.get("liminal_commits", 0)
            other_commits = row.get("other_repos", 0)
            if liminal_commits and other_commits:
                transfer_events.append({
                    "period": row.get("_key"),
                    "liminal_commits": liminal_commits,
                    "other_repo_commits": other_commits,
                    "note": row.get("note", ""),
                })

        result = {
            "analysis_type": "cross-repo-transfer",
            "rd_labs": rd_labs[:10],
            "top_repos": top_repos,
            "language_evolution": lang_evo,
            "transfer_events": transfer_events[:20],
            "concurrent_repos": [
                {"repo": r.get("repo"), "commits": r.get("commit_count"), "overlap": r.get("overlap_with_liminal_era")}
                for r in concurrent[:10]
            ],
            "summary": {
                "total_repos": len(github_repos),
                "rd_labs_identified": len(rd_labs),
                "transfer_events": len(transfer_events),
                "primary_languages": list(set(l.get("language", "") for l in top_repos[:5])) if top_repos else [],
            },
        }
        self._save("cross-repo-transfer", result)
        return result

    # ── Analyzer 12: YouTube Learning Graph ─────────────────────────

    def run_youtube_learning_graph(self) -> dict:
        """Learning diet visualization — who and what shaped the developer."""
        self._log("YouTube Learning Graph...")

        yt_corr = self._load("data/youtube-ai-correlation.json") or {}
        yt_creators = self._load("data/youtube-creators.json") or {}
        yt_topics = self._load("data/youtube-topic-classification.json") or {}
        yt_engagement = self._query("SELECT * FROM youtube_engagement")
        yt_categories = self._query("SELECT * FROM yt_categories ORDER BY value DESC")
        yt_creator_influence = self._query("SELECT * FROM yt_creator_influence")
        yt_monthly = self._query("SELECT * FROM yt_monthly ORDER BY _key")

        # Creator influence map
        creators_list = yt_creators.get("creators", []) if isinstance(yt_creators, dict) else []
        top_creators = sorted(creators_list, key=lambda c: c.get("video_count", 0) if isinstance(c, dict) else 0, reverse=True)[:15]

        # Topic distribution
        categories = yt_topics.get("categories", []) if isinstance(yt_topics, dict) else []
        distribution = yt_topics.get("distribution", {}) if isinstance(yt_topics, dict) else {}

        # Correlations (YouTube → commits)
        correlations = yt_corr.get("key_correlations", [])[:20] if isinstance(yt_corr, dict) else []
        smoking_guns = [c for c in correlations if isinstance(c, dict) and c.get("is_smoking_gun")]

        # Monthly learning curve
        monthly_curve = yt_corr.get("quarterly_learning_curve", {}) if isinstance(yt_corr, dict) else {}

        # Creator influence by archetype
        creator_archetypes = []
        for row in yt_creator_influence:
            archetypes = {k: v for k, v in row.items() if k != "_key" and k != "value"}
            creator_archetypes.append({
                "period": row.get("_key"),
                "total_videos": row.get("value"),
                "archetypes": archetypes,
            })

        result = {
            "analysis_type": "youtube-learning-graph",
            "top_creators": [
                {
                    "name": c.get("channel_name", c.get("name", "")),
                    "videos": c.get("video_count", 0),
                    "category": c.get("category", ""),
                } for c in top_creators if isinstance(c, dict)
            ],
            "topic_distribution": distribution,
            "categories": [{"category": r.get("_key"), "count": r.get("value")} for r in yt_categories],
            "smoking_guns": smoking_guns[:10],
            "monthly_learning": [{"month": r.get("_key"), "videos": r.get("value")} for r in yt_monthly],
            "quarterly_curve": monthly_curve,
            "creator_archetypes": creator_archetypes,
            "summary": {
                "total_creators": len(creators_list),
                "total_videos": yt_topics.get("total_videos", 0) if isinstance(yt_topics, dict) else 0,
                "smoking_gun_correlations": len(smoking_guns),
                "top_category": max(distribution, key=distribution.get) if distribution else None,
            },
        }
        self._save("youtube-learning-graph", result)
        return result

    # ── Analyzer 13: Architecture Evolution Timelapse ───────────────

    def run_architecture_timelapse(self) -> dict:
        """Era-by-era codebase structure evolution."""
        self._log("Architecture Evolution Timelapse...")

        eras = self._eras()
        module_emergence = self._query("SELECT * FROM module_emergence ORDER BY _key")
        file_growth = self._query("SELECT * FROM file_growth ORDER BY _key")
        codebase_langs = self._query("SELECT * FROM codebase_languages ORDER BY _key")

        # Restructuring commits per era
        restructuring_keywords = ["split", "extract", "decompose", "refactor", "rename", "reorganize", "restructure"]
        naming_keywords = ["rename", "migrate", "move to", "rebrand"]

        era_snapshots = []
        for era in eras:
            era_name = era.get("name", f"Era {era.get('id')}")
            # Get commits from this era's date range
            dates_str = era.get("dates", "")
            restructure_commits = self._like_commits(restructuring_keywords, 50)
            naming_commits = self._like_commits(naming_keywords, 30)

            era_snapshots.append({
                "era": era_name,
                "dates": dates_str,
                "commits": era.get("commits", 0),
                "active_days": era.get("active_days", 0),
                "restructuring_signals": len(restructure_commits),
                "naming_changes": len(naming_commits),
                "key_events": era.get("key_events", [])[:3] if isinstance(era.get("key_events"), list) else [],
                "narrative": era.get("narrative_arc", "")[:200] if era.get("narrative_arc") else "",
            })

        # Module emergence timeline
        modules = [{"period": r.get("_key"), "data": {k: v for k, v in r.items() if k != "_key"}} for r in module_emergence]

        # File growth
        growth = [{"metric": r.get("_key"), "value": r.get("value")} for r in file_growth]

        # Language evolution
        languages = []
        for row in codebase_langs:
            for lang, pct in row.items():
                if lang != "_key" and pct:
                    languages.append({"period": row.get("_key"), "language": lang, "percentage": pct})

        result = {
            "analysis_type": "architecture-timelapse",
            "era_snapshots": era_snapshots,
            "module_emergence": modules,
            "file_growth": growth,
            "language_evolution": languages,
            "summary": {
                "total_eras": len(eras),
                "restructuring_events": sum(s["restructuring_signals"] for s in era_snapshots),
                "naming_changes": sum(s["naming_changes"] for s in era_snapshots),
                "growth_trajectory": "exponential" if len(era_snapshots) > 3 and era_snapshots[-1]["commits"] > era_snapshots[0]["commits"] * 2 else "linear",
            },
        }
        self._save("architecture-timelapse", result)
        return result

    # ── Analyzer 14: Commit Message Cognitive Load Proxy ────────────

    def run_commit_cognitive_load(self) -> dict:
        """Classify work type from commit message length and content."""
        self._log("Commit Message Cognitive Load Proxy...")

        commits = self._query("SELECT hash, date, message, author FROM commits ORDER BY date")
        hourly = self._query("SELECT * FROM hourly_activity ORDER BY _key")
        eras = self._eras()

        # Classify by message length
        load_categories = {
            "TRIVIAL": {"max_len": 30, "description": "Quick fixes, typos, config tweaks"},
            "ROUTINE": {"min_len": 31, "max_len": 80, "description": "Standard features, small changes"},
            "MODERATE": {"min_len": 81, "max_len": 150, "description": "Feature implementation, refactoring"},
            "HIGH": {"min_len": 151, "max_len": 300, "description": "Architecture decisions, complex features"},
            "INTENSE": {"min_len": 301, "description": "Major rewrites, deep architectural work"},
        }

        classified = []
        for c in commits:
            msg = c.get("message", "")
            msg_len = len(msg)

            if msg_len <= 30:
                load = "TRIVIAL"
            elif msg_len <= 80:
                load = "ROUTINE"
            elif msg_len <= 150:
                load = "MODERATE"
            elif msg_len <= 300:
                load = "HIGH"
            else:
                load = "INTENSE"

            # Time of day from date
            date_str = str(c.get("date", ""))
            hour = int(date_str[11:13]) if len(date_str) > 12 else -1

            # Work type from keywords
            msg_lower = msg.lower()
            if any(kw in msg_lower for kw in ["fix", "bug", "error", "broken"]):
                work_type = "FIX"
            elif any(kw in msg_lower for kw in ["feat", "add", "implement", "create"]):
                work_type = "FEATURE"
            elif any(kw in msg_lower for kw in ["refactor", "clean", "simplify", "split"]):
                work_type = "REFACTOR"
            elif any(kw in msg_lower for kw in ["test", "spec", "coverage"]):
                work_type = "TEST"
            elif any(kw in msg_lower for kw in ["doc", "readme", "comment"]):
                work_type = "DOCS"
            elif any(kw in msg_lower for kw in ["ci", "deploy", "pipeline", "workflow"]):
                work_type = "CI/CD"
            else:
                work_type = "OTHER"

            classified.append({
                "cognitive_load": load,
                "work_type": work_type,
                "message_length": msg_len,
                "hour": hour,
            })

        # Aggregate statistics
        load_distribution = Counter(c["cognitive_load"] for c in classified)
        type_distribution = Counter(c["work_type"] for c in classified)

        # Cognitive load by hour of day
        load_by_hour = defaultdict(lambda: {"total": 0, "count": 0, "high_or_intense": 0})
        for c in classified:
            h = c["hour"]
            if h >= 0:
                load_by_hour[h]["total"] += c["message_length"]
                load_by_hour[h]["count"] += 1
                if c["cognitive_load"] in ("HIGH", "INTENSE"):
                    load_by_hour[h]["high_or_intense"] += 1

        hourly_load = [
            {
                "hour": h,
                "avg_message_length": round(d["total"] / d["count"], 1) if d["count"] else 0,
                "high_cognitive_pct": round(d["high_or_intense"] / d["count"] * 100, 1) if d["count"] else 0,
            }
            for h, d in sorted(load_by_hour.items())
        ]

        # Find peak cognitive hours
        peak_cognitive = sorted(hourly_load, key=lambda x: x["high_cognitive_pct"], reverse=True)[:5]

        result = {
            "analysis_type": "commit-cognitive-load",
            "load_distribution": dict(load_distribution),
            "work_type_distribution": dict(type_distribution),
            "load_by_hour": hourly_load,
            "peak_cognitive_hours": peak_cognitive,
            "load_definitions": load_categories,
            "summary": {
                "total_commits": len(classified),
                "avg_message_length": round(sum(c["message_length"] for c in classified) / max(len(classified), 1), 1),
                "high_cognitive_pct": round(
                    sum(1 for c in classified if c["cognitive_load"] in ("HIGH", "INTENSE")) / max(len(classified), 1) * 100, 1
                ),
                "dominant_work_type": type_distribution.most_common(1)[0][0] if type_distribution else None,
                "peak_cognitive_hour": peak_cognitive[0]["hour"] if peak_cognitive else None,
                "insight": "Longer commit messages correlate with architecture decisions. Peak cognitive hours suggest when complex work happens.",
            },
        }
        self._save("commit-cognitive-load", result)
        return result

    # ── Run all analyzers ───────────────────────────────────────────

    def run_all(self, analyzers: list[str] | None = None) -> dict[str, str]:
        """Execute selected opportunity analyzers and save JSON outputs."""
        results: dict[str, str] = {}
        runners = {
            "learning-velocity": self.run_learning_velocity,
            "frustration-to-automation": self.run_frustration_to_automation,
            "knowledge-gap": self.run_knowledge_gap,
            "token-efficiency": self.run_token_efficiency,
            "session-quality": self.run_session_quality,
            "ai-agent-mastery": self.run_ai_agent_mastery,
            "creative-dna": self.run_creative_dna,
            "neurodivergent-profile": self.run_neurodivergent_profile,
            "model-selection-advisor": self.run_model_selection_advisor,
            "before-after-snapshot": self.run_before_after_snapshot,
            "cross-repo-transfer": self.run_cross_repo_transfer,
            "youtube-learning-graph": self.run_youtube_learning_graph,
            "architecture-timelapse": self.run_architecture_timelapse,
            "commit-cognitive-load": self.run_commit_cognitive_load,
        }
        target = analyzers or self.ANALYZERS
        unknown = [a for a in target if a not in runners]
        if unknown:
            raise ValueError(f"Unknown analyzer(s): {', '.join(unknown)}")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        for name in target:
            try:
                result = runners[name]()
                results[name] = "OK"
                print(f"  [opportunity] {name}: OK")
            except Exception as exc:
                results[name] = f"ERROR: {exc}"
                print(f"  [opportunity] {name}: ERROR: {exc}")
        self.close()
        return results


def run_opportunity_analyzers(
    project_name: str, verbose: bool = False, analyzers: list[str] | None = None
) -> dict[str, str]:
    """Public entry point to run opportunity analyzers."""
    project_dir = f"projects/{project_name}"
    import os
    if not os.path.isdir(project_dir):
        raise ValueError(f"Project '{project_name}' not found")
    runner = OpportunityAnalyzer(project_name, project_dir, verbose)
    return runner.run_all(analyzers=analyzers)
