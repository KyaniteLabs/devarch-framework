# SDLC Gap Finder — Analysis Vector 1

> **Role:** Software Development Lifecycle auditor for {{project_name}}
> **Phase:** 3 (Parallel Analysis)
> **Input:** archaeology.db (commits, sessions, eras, audit tables)

---

## Objective

Identify missing or weak SDLC practices in {{project_name}} and rank them by return on investment (ROI). A "gap" is any standard practice that is absent, intermittent, or applied inconsistently across the project timeline.

---

## Input Data

Query the archaeology database for the following evidence:

### CI/CD Presence
```sql
-- Check for CI/CD related commits
SELECT date, message FROM commits
WHERE commits_fts MATCH 'CI CD pipeline deploy workflow github-actions'
ORDER BY date;
```
- Look for: `.github/workflows/` references, deployment commits, automated test runs
- Absence indicates: no CI/CD

### Test Coverage Trends
```sql
-- Check for test-related commits
SELECT date, message, repo FROM commits
WHERE commits_fts MATCH 'test spec coverage vitest jest mocha'
ORDER BY date;
```
- Look for: test addition patterns, coverage enforcement, test framework adoption
- Compute: test commit ratio = (test commits) / (total commits) per month

### Branch Protection
```sql
-- Check for branch/merge patterns
SELECT date, message FROM commits
WHERE commits_fts MATCH 'branch protect merge review PR pull-request'
ORDER BY date;
```
- Look for: branch creation, merge commits, PR references, review mentions

### Code Review Patterns
```sql
-- Check for review-related activity in sessions
SELECT timestamp, messages FROM sessions
WHERE sessions_fts MATCH 'review feedback approve request'
ORDER BY timestamp;
```
- Look for: human review requests, review feedback, approval workflows

### Refactoring Cycles
```sql
-- Check for refactoring commits
SELECT date, message FROM commits
WHERE commits_fts MATCH 'refactor clean restructure rewrite rename consolidate'
ORDER BY date;
```

---

## Analysis Methodology

1. **Catalog practices**: For each SDLC category (testing, CI/CD, review, documentation, refactoring, monitoring), classify as: PRESENT, INTERMITTENT, ABSENT, or EMERGING (recently adopted).

2. **Timeline mapping**: Plot when each practice first appeared (if at all). Identify stretches where the project operated without it.

3. **Effort estimation**: Rate effort to implement each missing practice on a 1-5 scale:
   - 1: Add a config file or single script
   - 2: Small workflow change (< 1 day)
   - 3: Moderate setup (1-3 days)
   - 4: Significant infrastructure (1-2 weeks)
   - 5: Cultural/organizational change (ongoing)

4. **Impact estimation**: Rate expected impact on a 1-5 scale:
   - 1: Cosmetic improvement
   - 2: Minor quality improvement
   - 3: Noticeable velocity or quality gain
   - 4: Major risk reduction or efficiency gain
   - 5: Project-critical (prevents common failure modes)

5. **ROI calculation**: ROI = Impact / Effort. Higher = better investment.

<!-- QA-2026-05: Finding 6 - Creative iteration exception for frustration heuristics -->
6. **Creative flow exception**:
   - Do NOT flag high modification counts on visual/design files as frustration
   - Creative iteration on UI/UX, styling, or visual assets is normal design work
   - Exclude file extensions: .css, .scss, .svg, .png, .jpg, .design, .fig, .sketch
   - Only flag frustration when modifications exceed expected iteration for the file type

---

## Output Schema

```json
{
  "project": "{{project_name}}",
  "analysis_date": "ISO-8601",
  "gaps": [
    {
      "practice": "string (e.g., 'CI/CD Pipeline')",
      "status": "PRESENT | INTERMITTENT | ABSENT | EMERGING",
      "evidence": [
        {
          "query": "SQL query or search term used",
          "result_count": 0,
          "sample": "representative commit or session excerpt"
        }
      ],
      "severity": "CRITICAL | HIGH | MEDIUM | LOW",
      "effort_to_implement": "1-5",
      "expected_impact": "1-5",
      "roi": "float (impact/effort)",
      "recommendation": "string — specific action to close this gap",
      "first_evidence_date": "ISO-8601 or null",
      "last_evidence_date": "ISO-8601 or null"
    }
  ],
  "summary": {
    "total_gaps": 0,
    "critical_gaps": 0,
    "top_3_roi": ["practice1", "practice2", "practice3"],
    "practices_present": ["list of well-established practices"],
    "practices_absent": ["list of missing practices"]
  }
}
```

---

## Quality Constraints

- **No speculation**: Every gap must cite at least one SQL query result. If a query returns zero rows, that IS the evidence (absence of evidence = evidence of absence).
- **No hallucinated tools**: Do not claim a tool exists unless a commit or file reference confirms it.
- **Conservative severity**: Default to MEDIUM unless evidence strongly supports CRITICAL or HIGH.
- **Actionable recommendations**: Each recommendation must be specific enough to execute in a single work session.
- **Evidence traceability**: Every claim links back to a commit hash, session ID, or data point.
- **Label uncertainty**: If evidence is ambiguous, mark as `[UNVERIFIED]` rather than guessing.
