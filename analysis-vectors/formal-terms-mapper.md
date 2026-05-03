# Formal Terms Mapper — Analysis Vector 4

> **Role:** Computer Science terminology bridge-builder for {{project_name}}
> **Phase:** 3 (Parallel Analysis)
> **Input:** archaeology.db (commits, sessions), source code (indexed symbols)

---

## Objective

Build a dictionary that maps {{project_name}}'s code naming conventions, variable names, module names, and architectural terms to their formal Computer Science or Software Engineering equivalents in academic literature and industry standard terminology.

---

## Input Data

### Function and Method Names from Commits
```sql
SELECT date, message FROM commits
WHERE commits_fts MATCH 'add implement create function method class module component'
ORDER BY date;
```

### Architectural Terms in Sessions
```sql
SELECT timestamp, messages FROM sessions
WHERE sessions_fts MATCH 'architecture pattern design structure framework strategy pipeline loop handler factory adapter observer'
ORDER BY timestamp;
```

### Module and File Names
```sql
SELECT date, message FROM commits
WHERE commits_fts MATCH 'rename refactor extract consolidate move split restructure'
ORDER BY date;
```
- Track naming evolution: what was a thing called initially vs. currently?

### Design Pattern References
```sql
SELECT timestamp, messages FROM sessions
WHERE sessions_fts MATCH 'pattern SOLID principle design factory singleton observer strategy command mediator'
ORDER BY timestamp;
```

### Source Code Symbol Names (from indexed code)
- Extract all exported function/class/method names
- Extract key variable names and constant names
- Extract file and directory names as architectural vocabulary

---

## Analysis Methodology

1. **Extract code vocabulary**: Harvest all named entities from the codebase:
   - Module names (e.g., `CompostMill`, `RalphLoop`, `OrganismLoop`)
   - Function names (e.g., `scoreReliable()`, `generateFull()`, `wrap()`)
   - Variable and constant names in key modules
   - File and directory names as architectural terms

2. **Map to formal CS terms**: For each code name, identify:
   - The closest formal CS/SE term (Design Patterns, SOLID, DDD, etc.)
   - Academic papers or textbooks that define the concept
   - Industry-standard naming conventions

3. **Naming evolution tracking**: Trace how names changed over time:
   - Initial (often poetic/creative) names
   - Intermediate renames
   - Current names
   - Whether the evolution moved toward or away from formal terminology

4. **Gap identification**: Find cases where:
   - The code implements a known pattern but the developer did not name it as such
   - The developer invented a name for something that already has a standard name
   - The naming obscures the underlying concept

5. **Similarity scoring**: Rate how close each code name is to its formal counterpart:
   - EXACT: Same name (e.g., `Factory` pattern named `Factory`)
   - CLOSE: Recognizable variant (e.g., `Provider` for `Strategy`)
   - METAPHORICAL: Creative name that maps to a formal concept
   - NOVEL: Genuinely new concept with no clear formal equivalent

---

## Output Schema

```json
{
  "project": "{{project_name}}",
  "analysis_date": "ISO-8601",
  "term_dictionary": [
    {
      "code_name": "string (e.g., 'CompostMill')",
      "code_context": "string (module purpose in one line)",
      "formal_term": "string (e.g., 'Processing Pipeline with Strategy Pattern')",
      "category": "DESIGN_PATTERN | ARCHITECTURE | ALGORITHM | DATA_STRUCTURE | PROCESS | NOVEL",
      "similarity_score": "EXACT | CLOSE | METAPHORICAL | NOVEL",
      "paper_reference": "string (e.g., 'GoF p. 315, Pipeline Pattern in Fowler 2017')",
      "evidence": [
        {
          "source": "commit hash, session ID, or file path",
          "excerpt": "relevant excerpt"
        }
      ],
      "naming_evolution": [
        {
          "date": "ISO-8601",
          "name": "string",
          "trigger": "string (why it was renamed)"
        }
      ]
    }
  ],
  "naming_trajectory": {
    "direction": "TOWARD_FORMAL | STABLE | TOWARD_CREATIVE | MIXED",
    "evidence": "string",
    "poetic_to_pragmatic_ratio": "float 0-1"
  },
  "learning_opportunities": [
    {
      "concept": "string (formal term the developer should study)",
      "why": "string (what it would have improved)",
      "resource": "string (book, paper, or article recommendation)"
    }
  ],
  "summary": {
    "total_terms_mapped": 0,
    "exact_matches": 0,
    "metaphorical_names": 0,
    "novel_concepts": 0,
    "naming_trend": "string"
  }
}
```

---

## Quality Constraints

- **No forced mappings**: Not every creative name maps to a formal term. If there is no clear equivalent, classify as NOVEL.
- **Cite real references**: Paper references must be real, verifiable publications. Do not invent citations.
- **Distinguish naming from implementation**: A class called `Factory` that is not a Factory pattern is a naming mismatch, not a pattern usage.
- **Respect developer intent**: Creative names are not necessarily wrong. Document them neutrally.
- **Label speculation**: If a mapping is plausible but uncertain, mark as `[UNVERIFIED]`.
- **Academic humility**: Software engineering terminology is not universally agreed upon. Note when a term has multiple competing definitions.
