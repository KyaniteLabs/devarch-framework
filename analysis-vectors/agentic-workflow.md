# Agentic Workflow Analyzer — Analysis Vector 3

> **Role:** AI agent session analyst for {{project_name}}
> **Phase:** 3 (Parallel Analysis)
> **Input:** archaeology.db (sessions, commits, eras, hooks data)

---

## Objective

Analyze how the developer interacted with AI coding agents across {{project_name}}. Map session depth, autonomy evolution, tool usage patterns, hook effectiveness, and frustration-to-automation conversion over time.

---

## Input Data

### Session Depth Distribution
```sql
SELECT session_id, timestamp, human_message_count, messages
FROM sessions
ORDER BY timestamp;
```
- Compute: messages per session, session duration (if timestamps available)
- Classify: micro (<5 messages), standard (5-20), deep (20-50), marathon (50+)

### Autonomy Indicators
```sql
SELECT timestamp, messages FROM sessions
WHERE sessions_fts MATCH 'autonomously independent plan decide choose suggest'
ORDER BY timestamp;
```
- Look for: sessions where the agent planned independently vs. followed explicit instructions
- Track: ratio of human-initiated vs. agent-initiated actions over time

### Tool Usage Patterns
```sql
SELECT timestamp, messages FROM sessions
WHERE sessions_fts MATCH 'tool function call edit write read search grep glob bash'
ORDER BY timestamp;
```
- Identify: which tools are used most, which are introduced when, adoption curves

### Hook and Automation Usage
```sql
SELECT date, message FROM commits
WHERE commits_fts MATCH 'hook pre-commit post-commit automation trigger cron schedule'
ORDER BY date;
```
- Look for: hook creation commits, automation setup, custom tooling

### Frustration Indicators
```sql
SELECT timestamp, messages FROM sessions
WHERE sessions_fts MATCH 'frustrating stuck broken fail error wrong why retry again still'
ORDER BY timestamp;
```
- Identify: frustration spikes, what triggered them, how they were resolved

### Era-by-Era Session Metrics
```sql
SELECT e.name, e.dates, COUNT(s.session_id) as session_count
FROM eras e LEFT JOIN sessions s ON s.timestamp BETWEEN e.start_date AND e.end_date
GROUP BY e.name;
```

---

## Analysis Methodology

1. **Session taxonomy**: Classify every session into categories:
   - SCAFFOLDING: Setting up new infrastructure
   - BUILDING: Active feature development
   - DEBUGGING: Fixing bugs or errors
   - REFACTORING: Restructuring existing code
   - EXPLORING: Research, prototyping, learning
   - REVIEW: Code review, quality checks

2. **Autonomy evolution**: Track the progression from human-directed to agent-directed work:
   - Phase 1: Human gives step-by-step instructions
   - Phase 2: Human gives goals, agent plans execution
   - Phase 3: Agent identifies needs and acts proactively
   - Phase 4: Agent self-corrects and iterates autonomously

3. **Hook effectiveness**: For each hook/automation:
   - When was it created?
   - What frustration or error did it address?
   - Did the issue recur after hook creation? (measure effectiveness)

4. **Frustration-to-automation conversion**: Identify frustration events that were resolved by creating automation. Rate conversion rate over time.

5. **Memory and context usage**: Analyze how the developer uses memory files, CLAUDE.md, and project instructions to shape agent behavior.

---

## Output Schema

```json
{
  "project": "{{project_name}}",
  "analysis_date": "ISO-8601",
  "session_depth_distribution": {
    "micro_lt5": 0,
    "standard_5_20": 0,
    "deep_20_50": 0,
    "marathon_50_plus": 0,
    "median_messages_per_session": 0,
    "longest_session": { "session_id": "string", "message_count": 0 }
  },
  "session_taxonomy": {
    "SCAFFOLDING": 0,
    "BUILDING": 0,
    "DEBUGGING": 0,
    "REFACTORING": 0,
    "EXPLORING": 0,
    "REVIEW": 0
  },
  "autonomy_evolution": [
    {
      "era": "string (era name or date range)",
      "phase": "1 | 2 | 3 | 4",
      "evidence": "session or commit excerpt",
      "human_directed_pct": "0-100",
      "agent_directed_pct": "0-100"
    }
  ],
  "hook_effectiveness": [
    {
      "hook_name": "string",
      "created_date": "ISO-8601",
      "addressed_frustration": "string",
      "issue_recurrence_after_creation": 0,
      "effectiveness_score": "float 0-1"
    }
  ],
  "frustration_to_automation": {
    "total_frustration_events": 0,
    "automated_resolutions": 0,
    "conversion_rate": "float 0-1",
    "timeline": [
      {
        "date": "ISO-8601",
        "frustration": "string",
        "resolution": "string or null",
        "resolution_type": "AUTOMATION | MANUAL | UNRESOLVED"
      }
    ]
  },
  "summary": {
    "total_sessions_analyzed": 0,
    "peak_autonomy_era": "string",
    "most_effective_hook": "string",
    "dominant_session_type": "string",
    "key_insight": "string — single most important finding"
  }
}
```

---

## Quality Constraints

- **No mind-reading**: Do not infer developer emotion beyond what is explicitly stated. Use word frequency as proxy, not assertion.
- **Session classification requires evidence**: Every taxonomy assignment must cite a session excerpt.
- **Autonomy scoring is approximate**: Mark autonomy phase estimates as `[ESTIMATED]` — they are interpretive, not objective.
- **Hook effectiveness requires before/after data**: Do not claim a hook is effective unless you can show the issue decreased after its creation.
- **Respect privacy**: Quote only enough session text to support the claim. Do not dump entire sessions into output.
- **Label speculation**: Any interpretation not directly supported by data must be marked `[UNVERIFIED]`.
