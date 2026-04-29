# Formal Terms Mapper Vector

Identify usage of formal methods and academic terminology.

## Purpose

Detect formal methods, mathematical concepts, and academic language in development.

## Detection Patterns

### Formal Methods

Search for formal methods keywords:

- Patterns: proof, verify, correct, invariant, assertion, lemma, theorem
- Identify formal specification commits
- Track verification activities

### Mathematical Concepts

Search for math terminology:

- Patterns: algorithm, complexity, optimization, convergence, gradient
- Identify math-heavy commits
- Track theoretical work

### Academic Terms

Search for academic language:

- Patterns: hypothesis, experiment, benchmark, evaluation, metric
- Identify research-oriented commits
- Track publication or paper work

### Type Theory

Search for type theory indicators:

- Patterns: type, category, functor, monad, algebra
- Identify theoretical CS work
- Track advanced type usage

### Verification

Search for verification activities:

- Patterns: test, verify, check, assert, validate
- Identify verification-focused commits
- Track quality assurance

## Output Schema

```json
{
  "vector_name": "formal-terms-mapper",
  "findings": [
    {
      "type": "formal_methods",
      "description": "Proof verification in April",
      "evidence": ["commit hashes"],
      "confidence": "high",
      "terms_found": ["proof", "verify", "invariant"],
      "metrics": {
        "formal_commits": 8,
        "total_commits": 50
      }
    }
  ],
  "summary": {
    "total_findings": 4,
    "by_type": {
      "formal_methods": 2,
      "mathematical": 1,
      "academic": 1
    }
  }
}
```

## Confidence Levels

- High: Multiple formal terms with clear context
- Medium: Some formal terms present
- Low: Few or ambiguous terms
