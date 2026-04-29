# ML Pattern Mapper Vector

Identify machine learning development patterns.

## Purpose

Detect ML-specific activities: experiments, model updates, data changes, training runs.

## Detection Patterns

### Model Experiments

Search for experiment keywords:

- Patterns: experiment, exp, trial, baseline, ablation
- Identify experimental commits vs production
- Track experiment frequency

### Model Updates

Search for model change indicators:

- Patterns: model, weights, checkpoint, h5, pth, onnx
- Identify model version changes
- Track model evolution

### Data Changes

Search for data modifications:

- Patterns: data, dataset, preprocessing, cleaning, augmentation
- Identify data pipeline commits
- Track data schema changes

### Training Runs

Search for training indicators:

- Patterns: train, epoch, batch, loss, accuracy, validation
- Identify training-related commits
- Track training frequency

### Infrastructure

Search for ML infrastructure:

- Patterns: notebook, colab, pipeline, serving, inference
- Identify tooling and environment commits

## Output Schema

```json
{
  "vector_name": "ml-pattern-mapper",
  "findings": [
    {
      "type": "model_experiment",
      "description": "Ablation study in March",
      "evidence": ["commit hashes"],
      "confidence": "high",
      "metrics": {
        "experiment_commits": 12,
        "total_commits": 50
      }
    }
  ],
  "summary": {
    "total_findings": 5,
    "by_type": {
      "model_experiment": 2,
      "model_update": 1,
      "data_change": 1,
      "training_run": 1
    }
  }
}
```

## Confidence Levels

- High: Clear ML pattern with domain keywords
- Medium: Some ML indicators present
- Low: Insufficient evidence
