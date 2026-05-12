#!/usr/bin/env python3
"""
Content Engine for Dev-Archaeology Excavation Reports

Generates weekly excavation reports from archaeological analysis outputs.
This script scans project deliverables for new/changed analysis outputs and
generates publishable content in multiple formats.

Usage:
    python scripts/content/generate_excavation_report.py <project_name> [start_date] [end_date]

Example:
    python scripts/content/generate_excavation_report.py demo-project 2026-04-23 2026-04-30
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


class ContentEngine:
    """Main content generation engine for excavation reports."""

    def __init__(self, project_name: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
        self.project_name = project_name
        self.base_path = Path.cwd()
        self.project_path = self.base_path / "projects" / project_name
        self.deliverables_path = self.project_path / "deliverables"

        # Set date range
        if end_date:
            self.end_date = datetime.strptime(end_date, "%Y-%m-%d")
        else:
            self.end_date = datetime.now()

        if start_date:
            self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            self.start_date = self.end_date - timedelta(days=7)  # Default to last week

        self.content_output_path = self.deliverables_path / "content"
        self.content_output_path.mkdir(exist_ok=True)

    def load_json_file(self, filename: str) -> Optional[Dict[str, Any]]:
        """Load and parse a JSON file from deliverables."""
        file_path = self.deliverables_path / filename
        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load {filename}: {e}")
            return None

    def load_markdown_file(self, filename: str) -> Optional[str]:
        """Load a markdown file from deliverables."""
        file_path = self.deliverables_path / filename
        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r') as f:
                return f.read()
        except IOError as e:
            print(f"Warning: Could not load {filename}: {e}")
            return None

    def extract_commit_count(self) -> int:
        """Extract total commit count from canonical metrics."""
        metrics = self.load_json_file("canonical-metrics.json")
        if metrics and "total_commits" in metrics:
            return metrics["total_commits"]
        return 0

    def extract_signals_detected(self) -> int:
        """Extract count of signals from various analyses."""
        total_signals = 0

        # From source archaeologist
        source_data = self.load_json_file("analysis-source-archaeologist.json")
        if source_data:
            quality_traj = source_data.get("quality_trajectory", {})
            total_signals += quality_traj.get("evidence_count", 0)

            arch_drift = source_data.get("architecture_drift", {})
            total_signals += len(arch_drift.get("large_change_signals", []))
            total_signals += len(arch_drift.get("todo_or_stub_signals", []))

        # From ML pattern mapper
        ml_data = self.load_json_file("analysis-ml-pattern-mapper.json")
        if ml_data:
            mappings = ml_data.get("mappings", [])
            total_signals += len(mappings)

        return total_signals

    def count_analysis_vectors(self) -> tuple[int, int]:
        """Count available vs total analysis vectors."""
        analysis_files = [
            "analysis-source-archaeologist.json",
            "analysis-sdlc-gap-finder.json",
            "analysis-ml-pattern-mapper.json",
            "analysis-formal-terms-mapper.json",
            "analysis-youtube-correlator.json",
            "analysis-agentic-workflow.json"
        ]

        available = sum(1 for f in analysis_files if (self.deliverables_path / f).exists())
        return available, len(analysis_files)

    def extract_audit_status(self) -> str:
        """Extract audit status from AUDIT-REPORT.md."""
        audit_content = self.load_markdown_file("AUDIT-REPORT.md")
        if not audit_content:
            return "UNKNOWN"

        # Look for rating pattern
        rating_match = re.search(r'Overall Rating:\s*([A-Z][+-]?)', audit_content)
        if rating_match:
            rating = rating_match.group(1)
            # Convert to PASS/FAIL based on grade
            if rating in ['A+', 'A', 'A-', 'B+', 'B']:
                return f"PASS ({rating})"
            else:
                return f"FAIL ({rating})"

        return "UNKNOWN"

    def extract_key_insights(self) -> List[str]:
        """Extract top 3 findings from each analysis vector."""
        insights = []

        # From source archaeologist
        source_data = self.load_json_file("analysis-source-archaeologist.json")
        if source_data:
            quality = source_data.get("quality_trajectory", {})
            if quality.get("assessment"):
                insights.append(f"Quality Trajectory: {quality['assessment']}")

            arch_drift = source_data.get("architecture_drift", {})
            large_changes = arch_drift.get("large_change_signals", [])[:3]
            for change in large_changes:
                insights.append(f"Architecture Change: {change.get('message', 'Unknown')}")

        # From ML pattern mapper
        ml_data = self.load_json_file("analysis-ml-pattern-mapper.json")
        if ml_data:
            mappings = ml_data.get("mappings", [])[:3]
            for mapping in mappings:
                intuitive = mapping.get("intuitive_name", "Unknown")
                formal = mapping.get("formal_term", "Unknown")
                insights.append(f"Pattern Recognition: '{intuitive}' → {formal}")

        # From SDLC gap finder
        sdlc_data = self.load_json_file("analysis-sdlc-gap-finder.json")
        if sdlc_data:
            gaps = sdlc_data.get("gaps", [])[:3]
            for gap in gaps:
                practice = gap.get("practice", "Unknown")
                status = gap.get("status", "Unknown")
                insights.append(f"SDLC Practice: {practice} is {status}")

        return insights[:10]  # Limit to top 10

    def extract_agent_activity(self) -> Dict[str, Any]:
        """Extract agent activity from agentic workflow analysis."""
        agent_data = self.load_json_file("analysis-agentic-workflow.json")
        if not agent_data:
            return {}

        activity = {
            "total_sessions": agent_data.get("session_depth_distribution", {}).get("sessions_total", 0),
            "dominant_type": agent_data.get("summary", {}).get("dominant_session_type", "Unknown"),
            "agent_attribution": agent_data.get("agent_attribution", [])
        }

        return activity

    def extract_recommended_actions(self) -> List[str]:
        """Extract recommendations from SDLC gap finder."""
        sdlc_data = self.load_json_file("analysis-sdlc-gap-finder.json")
        if not sdlc_data:
            return []

        recommendations = []
        gaps = sdlc_data.get("gaps", [])

        # Sort by ROI and take top 5
        sorted_gaps = sorted(gaps, key=lambda x: x.get("roi", 0), reverse=True)[:5]

        for gap in sorted_gaps:
            practice = gap.get("practice", "Unknown")
            recommendation = gap.get("recommendation", "")
            roi = gap.get("roi", 0)

            if recommendation:
                recommendations.append(f"**{practice}** (ROI: {roi:.1f}): {recommendation}")

        return recommendations

    def generate_content_opportunities(self) -> List[str]:
        """Generate content suggestions based on findings."""
        opportunities = []

        # Get insights for context
        insights = self.extract_key_insights()
        source_data = self.load_json_file("analysis-source-archaeologist.json")
        ml_data = self.load_json_file("analysis-ml-pattern-mapper.json")

        # Blog post ideas
        opportunities.append("### Blog Post Ideas")

        if source_data:
            quality = source_data.get("quality_trajectory", {})
            if quality.get("assessment") == "IMPROVING":
                opportunities.append("- **The Quality Trajectory**: How code quality evolved over {0} commits".format(
                    self.extract_commit_count()
                ))

        if ml_data:
            mappings = ml_data.get("mappings", [])
            reinventions = [m for m in mappings if m.get("is_reinvention")]
            if reinventions:
                opportunities.append("- **Reinventing the Wheel**: Analysis of {0} patterns that could have used libraries".format(
                    len(reinventions)
                ))

        # Video ideas
        opportunities.append("\n### Video Ideas")
        opportunities.append("- **Archaeology Deep Dive**: Live walkthrough of the most interesting commits")
        opportunities.append("- **Pattern Recognition Tutorial**: Exploring the formal terms behind intuitive naming")

        # Social post ideas
        opportunities.append("\n### Social Media Thread Ideas")
        opportunities.append("- **Commit archaeology**: Most surprising finding from the analysis")
        opportunities.append("- **Architecture drift**: How the codebase evolved over time")
        opportunities.append("- **Agent activity breakdown**: Who (or what) is writing the code?")

        return opportunities

    def generate_excavation_report(self) -> str:
        """Generate the main excavation report in Markdown format."""
        report_date = self.end_date.strftime("%Y-%m-%d")
        week_start = self.start_date.strftime("%Y-%m-%d")
        week_end = self.end_date.strftime("%Y-%m-%d")

        # Extract data
        commit_count = self.extract_commit_count()
        signals_detected = self.extract_signals_detected()
        vectors_available, vectors_total = self.count_analysis_vectors()
        audit_status = self.extract_audit_status()
        key_insights = self.extract_key_insights()
        agent_activity = self.extract_agent_activity()
        recommended_actions = self.extract_recommended_actions()
        content_opportunities = self.generate_content_opportunities()

        # Build report
        report_lines = [
            f"# Excavation Report: Week of {week_start} to {week_end}",
            f"## Project: {self.project_name.title()}",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Analysis Period:** {week_start} to {week_end}",
            "",
            "---",
            "",
            "## This Week's Findings",
            "",
            f"This week's excavation of {self.project_name.title()} analyzed {commit_count} commits, "
            f"uncovering {signals_detected} significant signals across {vectors_available} analysis vectors. "
            f"The project demonstrates {'strong' if 'PASS' in audit_status else 'concerning'} development practices "
            f"with an audit status of {audit_status}.",
            "",
        ]

        # By the Numbers section
        report_lines.extend([
            "## By the Numbers",
            "",
            f"- **Total commits analyzed:** {commit_count:,}",
            f"- **New signals detected:** {signals_detected:,}",
            f"- **Analysis vectors run:** {vectors_available}/{vectors_total}",
            f"- **Audit status:** {audit_status}",
            "",
        ])

        # Key Insights section
        if key_insights:
            report_lines.extend([
                "## Key Insights",
                "",
            ])
            for insight in key_insights:
                report_lines.append(f"- {insight}")
            report_lines.append("")

        # Agent Activity section
        if agent_activity:
            report_lines.extend([
                "## Agent Activity",
                "",
                f"- **Total sessions analyzed:** {agent_activity.get('total_sessions', 0)}",
                f"- **Dominant session type:** {agent_activity.get('dominant_type', 'Unknown')}",
                "",
            ])

            attributions = agent_activity.get('agent_attribution', [])
            if attributions:
                report_lines.extend([
                    "**Top Contributors:**",
                    "",
                ])
                for attr in attributions[:5]:
                    author = attr.get('author', 'Unknown')
                    count = attr.get('cnt', 0)
                    report_lines.append(f"- {author}: {count} commits")
                report_lines.append("")

        # Recommended Actions section
        if recommended_actions:
            report_lines.extend([
                "## Recommended Actions",
                "",
            ])
            for action in recommended_actions:
                report_lines.append(f"- {action}")
            report_lines.append("")

        # Content Opportunities section
        if content_opportunities:
            report_lines.extend([
                "## Content Opportunities",
                "",
            ])
            report_lines.extend(content_opportunities)
            report_lines.append("")

        # Metadata section
        report_lines.extend([
            "---",
            "",
            "## Report Metadata",
            "",
            f"- **Project:** {self.project_name}",
            f"- **Date range:** {week_start} to {week_end}",
            f"- **Generated by:** Dev-Archaeology Content Engine",
            f"- **Source files:**",
            f"  - canonical-metrics.json",
            f"  - analysis-source-archaeologist.json",
            f"  - analysis-sdlc-gap-finder.json",
            f"  - analysis-ml-pattern-mapper.json",
            f"  - analysis-agentic-workflow.json",
            f"  - AUDIT-REPORT.md",
            "",
        ])

        return "\n".join(report_lines)

    def generate_twitter_thread(self) -> str:
        """Generate a Twitter/X thread outline."""
        commit_count = self.extract_commit_count()
        signals_detected = self.extract_signals_detected()
        audit_status = self.extract_audit_status()
        insights = self.extract_key_insights()[:5]

        thread_lines = [
            f"# Twitter Thread: {self.project_name.title()} Excavation Report",
            "",
            f"**Week of:** {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}",
            "",
            "---",
            "",
            "**Tweet 1 (Hook):**",
            "",
            f"Just analyzed {commit_count:,} commits from {self.project_name.title()} 🔍",
            "",
            f"Found {signals_detected} signals, ran {self.count_analysis_vectors()[0]} analysis vectors, ",
            f"and the audit status is {audit_status}.",
            "",
            f"Here's what the code archaeology uncovered 🧵👇",
            "",
        ]

        # Add insight tweets
        for i, insight in enumerate(insights[:5], 2):
            thread_lines.extend([
                f"**Tweet {i}:**",
                "",
                insight[:280] if len(insight) < 280 else insight[:277] + "...",
                "",
            ])

        # Call to action tweet
        thread_lines.extend([
            "**Tweet 7 (CTA):**",
            "",
            f"Want to see the full excavation report?",
            "",
            f"Check out the detailed analysis at: [LINK TO REPORT]",
            "",
            f"#DevArchaeology #CodeAnalysis #{self.project_name.title()}",
            "",
        ])

        return "\n".join(thread_lines)

    def generate_blog_draft(self) -> str:
        """Generate a blog post draft from the most interesting finding."""
        commit_count = self.extract_commit_count()
        insights = self.extract_key_insights()
        source_data = self.load_json_file("analysis-source-archaeologist.json")
        ml_data = self.load_json_file("analysis-ml-pattern-mapper.json")

        # Find the most interesting insight
        top_insight = insights[0] if insights else "Significant architectural evolution detected"

        blog_lines = [
            f"# Blog Post Draft: {top_insight[:60]}...",
            "",
            f"**Project:** {self.project_name.title()}",
            f"**Date:** {self.end_date.strftime('%B %d, %Y')}",
            "",
            "---",
            "",
            "## Introduction",
            "",
            f"This week, we dug into the {self.project_name.title()} codebase, analyzing {commit_count:,} commits ",
            f"spanning from {self.start_date.strftime('%B %d')} to {self.end_date.strftime('%B %d, %Y')}. ",
            f"What we found provides a fascinating glimpse into modern software development practices.",
            "",
            "## The Most Interesting Finding",
            "",
            f"**{top_insight}**",
            "",
            "This discovery stands out because it reveals...",
            "",
            "## What This Means",
            "",
            "## Broader Implications",
            "",
            "## Conclusion",
            "",
            f"Stay tuned for next week's excavation report as we continue to explore the {self.project_name.title()} codebase.",
            "",
            "---",
            "",
            "*This post was auto-generated by the Dev-Archaeology Content Engine based on automated code archaeology analysis.*",
            "",
        ]

        return "\n".join(blog_lines)

    def save_reports(self) -> Dict[str, str]:
        """Generate and save all reports."""
        report_date = self.end_date.strftime("%Y-%m-%d")

        # Generate reports
        excavation_report = self.generate_excavation_report()
        twitter_thread = self.generate_twitter_thread()
        blog_draft = self.generate_blog_draft()

        # Save excavation report
        excavation_path = self.content_output_path / f"excavation-report-{report_date}.md"
        with open(excavation_path, 'w') as f:
            f.write(excavation_report)

        # Save Twitter thread
        twitter_path = self.content_output_path / f"twitter-thread-{report_date}.md"
        with open(twitter_path, 'w') as f:
            f.write(twitter_thread)

        # Save blog draft
        blog_path = self.content_output_path / f"blog-draft-{report_date}.md"
        with open(blog_path, 'w') as f:
            f.write(blog_draft)

        return {
            "excavation_report": str(excavation_path),
            "twitter_thread": str(twitter_path),
            "blog_draft": str(blog_path)
        }


def main():
    """Main entry point for the content engine."""
    parser = argparse.ArgumentParser(
        description="Generate weekly excavation reports from archaeological analysis outputs"
    )
    parser.add_argument(
        "project_name",
        help="Name of the project to analyze (e.g., 'demo-project', 'demo-archaeology')"
    )
    parser.add_argument(
        "start_date",
        nargs="?",
        help="Start date for the report period (YYYY-MM-DD format)"
    )
    parser.add_argument(
        "end_date",
        nargs="?",
        help="End date for the report period (YYYY-MM-DD format)"
    )

    args = parser.parse_args()

    # Validate project exists
    project_path = Path.cwd() / "projects" / args.project_name
    if not project_path.exists():
        print(f"Error: Project '{args.project_name}' not found at {project_path}")
        sys.exit(1)

    # Create content engine
    engine = ContentEngine(args.project_name, args.start_date, args.end_date)

    # Generate reports
    print(f"Generating excavation report for {args.project_name}...")
    print(f"Period: {engine.start_date.strftime('%Y-%m-%d')} to {engine.end_date.strftime('%Y-%m-%d')}")

    saved_reports = engine.save_reports()

    print("\n✓ Reports generated successfully:")
    for report_type, path in saved_reports.items():
        print(f"  {report_type}: {path}")


if __name__ == "__main__":
    main()
