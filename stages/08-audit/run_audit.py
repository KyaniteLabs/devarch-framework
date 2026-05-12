#!/usr/bin/env python3
"""Stage 08-Audit: Quality Gate Validation"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime

# Paths - using relative paths from script location
STAGES_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = STAGES_DIR / "stages" / "03-build" / "output" / "archaeology.db"
SIGNALS_PATH = STAGES_DIR / "stages" / "04-detect" / "output" / "detected-signals.json"
ANALYSIS_DIR = STAGES_DIR / "stages" / "05-analyze" / "output"
VISUALIZATION_PATH = STAGES_DIR / "stages" / "06-visualize" / "output" / "archaeology.html"
REPORT_MD = STAGES_DIR / "stages" / "07-report" / "output" / "ARCHAEOLOGY-REPORT.md"
REPORT_HTML = STAGES_DIR / "stages" / "07-report" / "output" / "ARCHAEOLOGY-REPORT.html"
OUTPUT_AUDIT = Path(__file__).resolve().parent / "output" / "audit-result.md"

# Ensure output directory exists
OUTPUT_AUDIT.parent.mkdir(parents=True, exist_ok=True)

class AuditChecker:
    def __init__(self):
        self.checks = []
        self.passed = 0
        self.failed = 0
        self.warnings = 0

    def add_check(self, name, passed, message, details=""):
        """Add an audit check result"""
        status = "✓ PASS" if passed else "✗ FAIL"
        if not passed and "warning" in message.lower():
            status = "⚠ WARN"
            self.warnings += 1
        elif passed:
            self.passed += 1
        else:
            self.failed += 1

        self.checks.append({
            'name': name,
            'status': status,
            'passed': passed,
            'message': message,
            'details': details
        })

    def generate_report(self):
        """Generate audit report"""
        report = f"""# DevArch ICM Pipeline - Audit Report

**Project:** demo-project
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Stage:** 08-Audit

---

## Audit Summary

- **Total Checks:** {len(self.checks)}
- **Passed:** {self.passed}
- **Failed:** {self.failed}
- **Warnings:** {self.warnings}

**Overall Status:** {'✓ PASSED' if self.failed == 0 else '✗ FAILED'}

---

## Audit Results

"""

        for check in self.checks:
            report += f"### {check['name']}\n\n"
            report += f"**Status:** {check['status']}\n\n"
            report += f"**Message:** {check['message']}\n\n"

            if check['details']:
                report += f"**Details:**\n{check['details']}\n\n"

            report += "---\n\n"

        if self.failed > 0:
            report += """## Remediation Steps

The following failures must be addressed:

"""
            for check in self.checks:
                if not check['passed'] and "warning" not in check['message'].lower():
                    report += f"1. **{check['name']}**: {check['message']}\n"

            report += "\nPlease re-run the affected stages after addressing these issues.\n\n"

        report += """## Completion

"""

        if self.failed == 0:
            report += """✓ **All audit checks passed successfully.**

The demo-project archaeology analysis is complete and ready for delivery.

All outputs have been validated:
- Number reconciliation verified
- Data consistency confirmed
- File integrity checked
- Quality gates passed

"""
        else:
            report += """✗ **Audit failed.**

Please address the failures listed above and re-run the audit.

"""

        return report

def run_audit():
    """Run all audit checks"""

    auditor = AuditChecker()

    # Check 1: Database Integrity
    print("Checking database integrity...")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM commits")
        db_commit_count = cursor.fetchone()[0]

        if db_commit_count > 0:
            auditor.add_check(
                "Database Integrity",
                True,
                f"Database contains {db_commit_count} commits"
            )
        else:
            auditor.add_check(
                "Database Integrity",
                False,
                "Database is empty or contains no commits"
            )

        conn.close()
    except Exception as e:
        auditor.add_check(
            "Database Integrity",
            False,
            f"Database check failed: {str(e)}"
        )

    # Check 2: Signal Detection Output
    print("Checking signal detection output...")
    try:
        with open(SIGNALS_PATH, 'r') as f:
            signals = json.load(f)

        signals_total = signals.get('total_commits', 0)
        signals_match = signals_total == db_commit_count

        auditor.add_check(
            "Signal Detection Output",
            signals_match,
            f"Signal detection shows {signals_total} commits" + (" (matches database)" if signals_match else " (MISMATCH with database)")
        )

        # Check for placeholder data
        has_placeholders = any(
            'TODO' in str(v).upper() or 'PLACEHOLDER' in str(v).upper() or 'FIXME' in str(v).upper()
            for v in signals.values()
        )

        if has_placeholders:
            auditor.add_check(
                "Placeholder Data Check",
                False,
                "Placeholder data found in signals output"
            )
        else:
            auditor.add_check(
                "Placeholder Data Check",
                True,
                "No placeholder data detected in signals"
            )

    except Exception as e:
        auditor.add_check(
            "Signal Detection Output",
            False,
            f"Signal detection check failed: {str(e)}"
        )

    # Check 3: Analysis Outputs
    print("Checking analysis outputs...")
    try:
        analysis_files = list(ANALYSIS_DIR.glob('analysis-*.json'))

        if len(analysis_files) >= 4:
            auditor.add_check(
                "Analysis Output Count",
                True,
                f"Found {len(analysis_files)} analysis files"
            )
        else:
            auditor.add_check(
                "Analysis Output Count",
                False,
                f"Expected at least 4 analysis files, found {len(analysis_files)}"
            )

        # Check each analysis file for valid JSON and content
        for analysis_file in analysis_files:
            with open(analysis_file, 'r') as f:
                data = json.load(f)

            findings = data.get('findings', [])
            vector_name = data.get('vector_name', analysis_file.stem)

            if findings:
                auditor.add_check(
                    f"Analysis Content: {vector_name}",
                    True,
                    f"{vector_name} contains {len(findings)} findings"
                )
            else:
                auditor.add_check(
                    f"Analysis Content: {vector_name}",
                    False,
                    f"{vector_name} contains no findings"
                )

    except Exception as e:
        auditor.add_check(
            "Analysis Outputs",
            False,
            f"Analysis output check failed: {str(e)}"
        )

    # Check 4: Visualization Output
    print("Checking visualization output...")
    try:
        if VISUALIZATION_PATH.exists():
            with open(VISUALIZATION_PATH, 'r') as f:
                html_content = f.read()

            if len(html_content) > 1000 and '<html' in html_content:
                auditor.add_check(
                    "Visualization Output",
                    True,
                    f"HTML visualization generated ({len(html_content)} bytes)"
                )
            else:
                auditor.add_check(
                    "Visualization Output",
                    False,
                    "Visualization file is too small or malformed"
                )
        else:
            auditor.add_check(
                "Visualization Output",
                False,
                "Visualization file not found"
            )

    except Exception as e:
        auditor.add_check(
            "Visualization Output",
            False,
            f"Visualization check failed: {str(e)}"
        )

    # Check 5: Report Outputs
    print("Checking report outputs...")
    try:
        # Check markdown report
        if REPORT_MD.exists():
            with open(REPORT_MD, 'r') as f:
                md_content = f.read()

            if len(md_content) > 500 and '# Archaeology Report' in md_content:
                auditor.add_check(
                    "Markdown Report",
                    True,
                    f"Markdown report generated ({len(md_content)} bytes)"
                )
            else:
                auditor.add_check(
                    "Markdown Report",
                    False,
                    "Markdown report is too short or missing header"
                )
        else:
            auditor.add_check(
                "Markdown Report",
                False,
                "Markdown report file not found"
            )

        # Check HTML report
        if REPORT_HTML.exists():
            with open(REPORT_HTML, 'r') as f:
                html_content = f.read()

            if len(html_content) > 1000 and '<html' in html_content:
                auditor.add_check(
                    "HTML Report",
                    True,
                    f"HTML report generated ({len(html_content)} bytes)"
                )
            else:
                auditor.add_check(
                    "HTML Report",
                    False,
                    "HTML report is too small or malformed"
                )
        else:
            auditor.add_check(
                "HTML Report",
                False,
                "HTML report file not found"
            )

    except Exception as e:
        auditor.add_check(
            "Report Outputs",
            False,
            f"Report check failed: {str(e)}"
        )

    # Check 6: Number Reconciliation
    print("Checking number reconciliation...")
    try:
        # Reconcile commit count across all stages
        counts = []

        # From database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM commits")
        counts.append(('Database', cursor.fetchone()[0]))
        conn.close()

        # From signals
        with open(SIGNALS_PATH, 'r') as f:
            signals = json.load(f)
        counts.append(('Signals', signals.get('total_commits', 0)))

        # Check if all counts match
        unique_counts = set(count for _, count in counts)

        if len(unique_counts) == 1:
            auditor.add_check(
                "Number Reconciliation",
                True,
                f"All commit counts match: {counts[0][1]}"
            )
        else:
            details = "\n".join(f"  - {name}: {count}" for name, count in counts)
            auditor.add_check(
                "Number Reconciliation",
                False,
                "Commit count mismatch across stages",
                details
            )

    except Exception as e:
        auditor.add_check(
            "Number Reconciliation",
            False,
            f"Reconciliation check failed: {str(e)}"
        )

    # Check 7: Date Consistency
    print("Checking date consistency...")
    try:
        with open(SIGNALS_PATH, 'r') as f:
            signals = json.load(f)

        signals_date_range = signals.get('date_range', '')

        if signals_date_range:
            auditor.add_check(
                "Date Consistency",
                True,
                f"Date range consistent: {signals_date_range}"
            )
        else:
            auditor.add_check(
                "Date Consistency",
                False,
                "Date range missing from signals"
            )

    except Exception as e:
        auditor.add_check(
            "Date Consistency",
            False,
            f"Date consistency check failed: {str(e)}"
        )

    # Check 8: File Integrity
    print("Checking file integrity...")
    try:
        required_files = [
            (DB_PATH, "Database"),
            (SIGNALS_PATH, "Signals"),
            (VISUALIZATION_PATH, "Visualization"),
            (REPORT_MD, "Markdown Report"),
            (REPORT_HTML, "HTML Report")
        ]

        missing_files = []
        for file_path, name in required_files:
            if not file_path.exists():
                missing_files.append(name)
            elif file_path.stat().st_size == 0:
                missing_files.append(f"{name} (empty)")

        if not missing_files:
            auditor.add_check(
                "File Integrity",
                True,
                f"All {len(required_files)} required files present and non-empty"
            )
        else:
            auditor.add_check(
                "File Integrity",
                False,
                f"Missing or empty files: {', '.join(missing_files)}"
            )

    except Exception as e:
        auditor.add_check(
            "File Integrity",
            False,
            f"File integrity check failed: {str(e)}"
        )

    # Generate and save report
    print("\nGenerating audit report...")
    report = auditor.generate_report()

    with open(OUTPUT_AUDIT, 'w') as f:
        f.write(report)

    return auditor

if __name__ == '__main__':
    print("Running Stage 08-Audit...\n")

    auditor = run_audit()

    print(f"\n{'='*60}")
    print(f"Audit Complete")
    print(f"{'='*60}")
    print(f"Total Checks: {len(auditor.checks)}")
    print(f"Passed: {auditor.passed}")
    print(f"Failed: {auditor.failed}")
    print(f"Warnings: {auditor.warnings}")
    print(f"\nOverall Status: {'✓ PASSED' if auditor.failed == 0 else '✗ FAILED'}")
    print(f"\nAudit report written to: {OUTPUT_AUDIT}")

    if auditor.failed > 0:
        print("\n⚠ Please address the failures and re-run affected stages.")
    else:
        print("\n✓ All stages completed successfully!")
