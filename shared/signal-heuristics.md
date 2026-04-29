# Signal Detection Heuristics

Five signal types that DevArch detects in commit history.

## Signal Types

### 1. Gap Detection

**Definition**: Periods of inactivity exceeding the threshold.

**Detection**: No commits for N days (default N=3).

**Threshold**: Configurable via signal_gap_threshold in project.json.

**Output**: List of gap periods with start/end dates and duration.

### 2. Velocity Shifts

**Definition**: Significant changes in commit frequency.

**Detection**: Compare commits per week before/after a moving window.

**Threshold**: 50% increase or decrease in velocity.

**Output**: Periods with velocity change, before/after rates.

### 3. Author Changes

**Definition**: Commits from different authors than the primary developer.

**Detection**: Author email differs from primary developer email.

**Threshold**: Any non-primary author.

**Output**: List of external commits with author, date, files changed.

### 4. Scope Changes

**Definition**: Significant changes in files touched per commit.

**Detection**: Compare files changed per commit before/after moving window.

**Threshold**: 2x increase or decrease in average files per commit.

**Output**: Periods with scope shift, before/after averages.

### 5. Supplementary Correlation

**Definition**: Patterns between commits and external data sources.

**Detection**: Date-join commits against supplementary data, identify correlations.

**Threshold**: Any data point within 24 hours of a commit.

**Output**: List of correlated events with commit, external data, correlation type.

## Output Format

All signals output to stages/04-detect/output/detected-signals.json as a list with type, date, and metadata.
