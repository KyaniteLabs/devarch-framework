# Stage 05-Analyze

Run analysis vectors on database and detected signals.

## Inputs

- stages/03-build/output/archaeology.db
- stages/04-detect/output/detected-signals.json
- Supplementary data (if configured in project.json)

## Process

1. Load database and signals
2. Run SDLC gap finder vector
3. Run ML pattern mapper vector
4. Run formal terms mapper vector
5. Run source archaeologist vector
6. Run supplementary correlator vector (if supplementary data exists)
7. Output each vector result to separate JSON file

## Checkpoint

After running all vectors, review findings before proceeding to visualization.

Confirm analysis results are meaningful and align with project goals.

## Outputs

- stages/05-analyze/output/analysis-sdlc-gap-finder.json
- stages/05-analyze/output/analysis-ml-pattern-mapper.json
- stages/05-analyze/output/analysis-formal-terms-mapper.json
- stages/05-analyze/output/analysis-source-archaeologist.json
- stages/05-analyze/output/analysis-supplementary-correlator.json (if applicable)

## Vector Output Schema (generic)

```json
{
  "vector_name": "string",
  "findings": [
    {
      "type": "string",
      "description": "string",
      "evidence": [],
      "confidence": "high|medium|low"
    }
  ],
  "summary": {
    "total_findings": 0,
    "by_type": {}
  }
}
```

## Success Criteria

- All configured vectors executed
- JSON outputs valid
- Checkpoint review completed

## Next Stage

After checkpoint review, proceed to 06-visualize.
