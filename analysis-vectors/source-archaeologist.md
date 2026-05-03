# Source Code Archaeologist — Analysis Vector 5

> **Role:** Line-level code quality analyst for {{project_name}}
> **Phase:** 3 (Parallel Analysis)
> **Input:** archaeology.db (commits, codebase growth, audit tables), source code (indexed)

---

## Objective

Perform line-level analysis of {{project_name}}'s source code to identify specific improvements ranked by effort-to-impact ratio. Focus on quality trajectory, dead code detection, refactoring opportunities, and structural issues.

---

## Input Data

### Quality Trajectory from Commits
```sql
SELECT date, message FROM commits
WHERE commits_fts MATCH 'fix bug refactor clean remove delete dead unused consolidate simplify'
ORDER BY date;
```
- Track: ratio of fix/refactor commits to feature commits over time

### Codebase Growth Patterns
```sql
SELECT * FROM monthly_velocity ORDER BY month;
```
- Track: files added vs. modified over time
- Compute: growth rate acceleration/deceleration

### Dead Code Indicators
```sql
SELECT date, message FROM commits
WHERE commits_fts MATCH 'unused dead remove delete comment out stub placeholder TODO FIXME'
ORDER BY date;
```
- Look for: modules mentioned but never imported, exported functions never called

### Test Quality Signals
```sql
SELECT date, message FROM commits
WHERE commits_fts MATCH 'test spec coverage assert expect mock stub'
ORDER BY date;
```
- Track: test addition patterns, coverage enforcement adoption

### Architecture Drift
```sql
SELECT date, message FROM commits
WHERE commits_fts MATCH 'move rename restructure reorganize split extract'
ORDER BY date;
```
- Look for: repeated restructuring of the same areas (instability signal)

### Source Code Symbols (from indexed code)
- Identify: large files (>300 lines), deeply nested functions, high cyclomatic complexity
- Identify: modules with no tests, modules imported once, circular dependencies

---

## Analysis Methodology

1. **Quality trajectory**: Plot the ratio of quality-improving commits (fix, refactor, test) to quality-degrading commits (feat, hack, workaround) over time. Identify inflection points.

2. **Dead code detection**:
   - Modules/files committed but never referenced again
   - Exported symbols never imported elsewhere
   - TODO/FIXME comments that were never resolved
   - Commented-out code blocks left behind

3. **Hotspot identification**: Files or modules that are modified disproportionately often. These are either:
   - Core infrastructure (expected) OR
   - Unstable modules that need refactoring (problematic)

4. **Complexity assessment**: For each module, estimate:
   - Lines of code (LOC)
   - Number of exports (API surface)
   - Depth of call tree (how many layers deep)
   - Number of dependencies (coupling)

5. **Effort-to-impact ranking**: For each identified improvement:
   - Effort: LOW (<1 hour), MEDIUM (1-4 hours), HIGH (4+ hours)
   - Impact: LOW (cosmetic), MEDIUM (maintainability), HIGH (correctness/performance), CRITICAL (bug risk)

---

## Output Schema

```json
{
  "project": "{{project_name}}",
  "analysis_date": "ISO-8601",
  "quality_trajectory": {
    "overall_trend": "IMPROVING | STABLE | DECLINING | VOLATILE",
    "inflection_points": [
      {
        "date": "ISO-8601",
        "direction": "IMPROVING | DECLINING",
        "trigger": "string (what caused the change)"
      }
    ],
    "quality_commit_ratio_by_month": [
      { "month": "YYYY-MM", "ratio": "float 0-1" }
    ]
  },
  "improvements": [
    {
      "file": "string (file path)",
      "line_range": "string (e.g., '45-67')",
      "issue_type": "DEAD_CODE | HIGH_COMPLEXITY | MISSING_TESTS | COUPLING | DUPLICATION | NAMING | ANTIPATTERN",
      "issue": "string (specific description of the problem)",
      "effort": "LOW | MEDIUM | HIGH",
      "impact": "LOW | MEDIUM | HIGH | CRITICAL",
      "effort_to_impact_score": "float (impact_weight / effort_weight)",
      "recommendation": "string (specific fix action)",
      "evidence": "string (commit or code reference)"
    }
  ],
  "dead_code": [
    {
      "module_or_file": "string",
      "type": "UNUSED_EXPORT | UNREFERENCED_FILE | COMMENTED_CODE | STUB | TODO_NEVER_DONE",
      "evidence": "commit or analysis reference",
      "safe_to_remove": "boolean"
    }
  ],
  "hotspots": [
    {
      "file": "string",
      "commit_frequency": 0,
      "instability_score": "float 0-1",
      "recommendation": "string"
    }
  ],
  "summary": {
    "total_improvements_identified": 0,
    "critical_issues": 0,
    "dead_code_items": 0,
    "top_5_roi_improvements": ["list of improvement descriptions"],
    "quality_trend": "string"
  }
}
```

---

## Quality Constraints

- **Specific over vague**: Every improvement must name a specific file and (when possible) a line range. No "the codebase could be cleaner."
- **Evidence-based dead code**: Claiming code is dead requires evidence (no imports, no references). Do not flag code as dead just because it looks unused.
- **No style nits**: Focus on structural and correctness issues, not formatting preferences.
- **Effort estimates must be honest**: LOW effort means the fix is straightforward, not that it is unimportant.
- **Impact must be justified**: CRITICAL impact requires evidence of actual or probable bugs.
- **Label speculation**: If an issue is suspected but not confirmed, mark as `[UNVERIFIED]`.
- **Respect legacy context**: Code that looks bad now may have been the right decision at the time. Note the context.
