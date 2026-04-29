# Analysis Vector Registry

Available analysis vectors for stage 05-analyze.

## Vectors

### 1. SDLC Gap Finder

Identifies gaps in software development lifecycle practices (tests, docs, reviews).

**Inputs**: archaeology.db, detected-signals.json

**Outputs**: analysis-sdlc-gap-finder.json

**Detection Pattern**: Searches commit messages for test/doc patterns, calculates coverage ratios.

### 2. ML Pattern Mapper

Identifies machine learning development patterns (experiments, model updates, data changes).

**Inputs**: archaeology.db, detected-signals.json

**Outputs**: analysis-ml-pattern-mapper.json

**Detection Pattern**: Searches for model, training, data, experiment keywords in messages and files.

### 3. Formal Terms Mapper

Identifies usage of formal methods, mathematical concepts, academic terminology.

**Inputs**: archaeology.db, detected-signals.json

**Outputs**: analysis-formal-terms-mapper.json

**Detection Pattern**: Searches for formal methods, proofs, theorems, verification keywords.

### 4. Source Archaeologist

Deep dive into code evolution, file lifecycle, and refactoring patterns.

**Inputs**: archaeology.db, detected-signals.json

**Outputs**: analysis-source-archaeologist.json

**Detection Pattern**: Tracks file additions/deletions/renames, calculates churn metrics.

### 5. Supplementary Correlator

Cross-references commit history with external data sources.

**Inputs**: archaeology.db, detected-signals.json, supplementary data (if configured)

**Outputs**: analysis-supplementary-correlator.json

**Detection Pattern**: Date-join commits against supplementary data, identifies temporal correlations.

## Running Vectors

All vectors run during stage 05-analyze. Each produces a separate JSON output file.

Vectors can be run individually for targeted analysis.

## Adding Custom Vectors

To add a new vector:

1. Create detection logic script
2. Add to registry in shared/analysis-vector-registry.md
3. Output to stages/05-analyze/output/analysis-<name>.json
