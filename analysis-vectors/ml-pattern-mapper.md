# ML/AI Pattern Mapper — Analysis Vector 2

> **Role:** Machine Learning / AI pattern detector for {{project_name}}
> **Phase:** 3 (Parallel Analysis)
> **Input:** archaeology.db (commits, sessions, eras), source code (indexed)

---

## Objective

Scan {{project_name}} for code patterns, architectures, and algorithms that resemble formal ML/AI techniques — whether the developer was aware of the connection or not. Identify reinvented algorithms, map intuitive implementations to formal terminology, and estimate knowledge-gap waste.

---

## Input Data

### Commit Messages with ML-Adjacent Terms
```sql
SELECT date, message, repo FROM commits
WHERE commits_fts MATCH 'score rank threshold weight sample reward explore exploit diversity fitness evolve mutate select'
ORDER BY date;
```

### Module and Function Names
```sql
SELECT date, message FROM commits
WHERE commits_fts MATCH 'model embedding cluster similarity vector feature neural layer network attention'
ORDER BY date;
```

### Session Discussions of AI/ML Topics
```sql
SELECT timestamp, messages FROM sessions
WHERE sessions_fts MATCH 'training learning model neural network embedding clustering algorithm'
ORDER BY timestamp;
```

### Architecture Patterns (from indexed code)
Search for modules with these patterns:
- Scoring/ranking systems with weighted criteria
- Exploration-exploitation trade-offs (A/B testing, selection strategies)
- Embedding or similarity computation
- Evolutionary/genetic algorithm structures (selection, mutation, crossover)
- Thompson Sampling or Bayesian update patterns
- Prompt engineering or chain-of-thought structures
- Feedback loop architectures (rating, evaluation, iteration)

---

## Analysis Methodology

1. **Pattern detection**: For each module or commit cluster, identify whether the code implements a known ML/AI pattern. Check for:
   - Mathematical operations (dot products, cosine similarity, softmax, entropy)
   - Iterative optimization loops with convergence criteria
   - Probabilistic selection (weighted random, Thompson Sampling)
   - Feature extraction from unstructured data
   - Evaluation/scoring functions with tunable weights

2. **Formal mapping**: For each detected pattern, identify the closest formal term:
   - What the developer likely called it (intuitive name)
   - What the academic/industry term is (formal name)
   - How close the implementation is to the canonical version

3. **Confidence scoring**: Rate confidence of each mapping:
   - HIGH: Code implements the algorithm correctly (matches textbook definition)
   - MEDIUM: Code captures the essence but with non-standard implementation
   - LOW: Superficial resemblance — may be coincidence

4. **Reinvention detection**: Flag cases where the developer built something from scratch that a well-known library or algorithm already solves.

5. **Token waste estimation**: For reinvented algorithms, estimate how many LLM tokens were spent debugging vs. what a direct library usage would have required.

---

## Output Schema

```json
{
  "project": "{{project_name}}",
  "analysis_date": "ISO-8601",
  "mappings": [
    {
      "intuitive_name": "string (e.g., 'scoring system', 'soup evolution')",
      "formal_term": "string (e.g., 'Thompson Sampling', 'Evolutionary Strategy')",
      "confidence": "HIGH | MEDIUM | LOW",
      "module_or_file": "string (file path or module name)",
      "evidence": [
        {
          "source": "commit hash or session ID",
          "excerpt": "relevant code snippet or message excerpt"
        }
      ],
      "similarity_to_canonical": "float 0-1 (how close to textbook implementation)",
      "is_reinvention": "boolean (built from scratch when library exists)",
      "library_alternative": "string or null (e.g., 'scikit-learn Bandit, OpenAI Evals')",
      "estimated_token_waste": "integer or null (tokens spent on reinvention)"
    }
  ],
  "reinventions": [
    {
      "reinvented_what": "string",
      "could_have_used": "string (library/algorithm name)",
      "effort_wasted": "LOW | MEDIUM | HIGH",
      "evidence": "commit or session reference"
    }
  ],
  "summary": {
    "total_patterns_found": 0,
    "high_confidence_mappings": 0,
    "reinventions_detected": 0,
    "estimated_total_token_waste": 0,
    "top_learning_opportunities": ["formal terms the developer should study"]
  }
}
```

---

## Quality Constraints

- **Evidence required**: Every mapping must cite at least one commit hash or session excerpt. No pattern claims from thin air.
- **Conservative confidence**: Default to MEDIUM. Reserve HIGH for implementations that match published algorithm descriptions.
- **No false equivalence**: A simple if/else is not a "decision tree." A weighted sum is not a "neural network." Be honest about scale.
- **Label speculation**: If a mapping is plausible but unconfirmed, mark as `[UNVERIFIED]`.
- **Distinguish inspiration from implementation**: The developer may have been *inspired* by ML concepts without implementing them. Document both.
- **No buzzword inflation**: Do not upgrade simple heuristics to ML terminology. A scoring function with weights is a weighted heuristic, not necessarily "learning."
