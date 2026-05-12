# Dev-Archaeology Integration Hooks

This directory contains integration hooks for external tools to trigger DevArch analysis.

## Scout Hook

The `scout_hook.py` script allows external tools (research-scout, CI/CD, etc.) to automatically trigger archaeological analysis on discovered repositories.

### Features

- **Multiple input modes**: CLI arguments, JSON stdin, or programmatic Python calls
- **Automatic cloning**: Clones repositories from URLs to temporary directories
- **Full pipeline execution**: init → mine → build-db → signals → analyze
- **Structured JSON output**: Returns status, metrics, and artifact paths
- **Graceful error handling**: Continues through non-critical failures (signals, analysis)
- **Automatic cleanup**: Removes temporary clones by default

### Usage

#### CLI Mode (Repository URL)

```bash
python3 scripts/integrations/scout_hook.py \
  --repo-url https://github.com/user/repo \
  --project-name my-project
```

#### CLI Mode (Local Repository)

```bash
python3 scripts/integrations/scout_hook.py \
  --repo-path /path/to/local/repo \
  --project-name my-project
```

#### Stdin Mode (JSON Input)

```bash
echo '{"url": "https://github.com/user/repo", "name": "my-project"}' | \
  python3 scripts/integrations/scout_hook.py --stdin
```

#### Keep Cloned Repository

```bash
python3 scripts/integrations/scout_hook.py \
  --repo-url https://github.com/user/repo \
  --project-name my-project \
  --keep
```

#### Custom Clone Directory

```bash
python3 scripts/integrations/scout_hook.py \
  --repo-url https://github.com/user/repo \
  --project-name my-project \
  --clone-dir /tmp/archaeology-clones
```

### Input Format

#### CLI Arguments

- `--repo-url`: Repository URL to clone and analyze
- `--repo-path`: Local repository path (skips cloning)
- `--project-name`: Name for the archaeology project (required)
- `--clone-dir`: Directory for cloned repos (default: temp dir)
- `--keep`: Keep cloned repository after analysis
- `--stdin`: Read input as JSON from stdin

#### JSON Stdin Format

```json
{
  "url": "https://github.com/user/repo",
  "path": "/path/to/local/repo",
  "name": "my-project",
  "keep": false,
  "clone_dir": "/tmp/archaeology-clones"
}
```

Either `url` or `path` must be provided. `name` is required.

### Output Format

The script outputs JSON to stdout with the following structure:

```json
{
  "project_name": "my-project",
  "repo_path": "/path/to/repo",
  "repo_url": "https://github.com/user/repo",
  "status": "complete",
  "steps": {
    "init": {
      "status": "success",
      "message": "Created project 'my-project' at projects/my-project/"
    },
    "mine": {
      "status": "success",
      "message": "Extracted 123 commits to projects/my-project/data/github-commits.csv"
    },
    "build_db": {
      "status": "success",
      "message": "Database built at projects/my-project/data/archaeology.db"
    },
    "signals": {
      "status": "success",
      "message": "Detected 5 signals across 3 clusters."
    },
    "analyze": {
      "status": "success",
      "message": "  sdlc-gap-finder: projects/my-project/deliverables/analysis-sdlc-gap-finder.json\n  ..."
    }
  },
  "metrics": {
    "commit_count": 123,
    "db_built": true,
    "signal_count": 5,
    "analysis_count": 6
  },
  "artifacts": {
    "project_dir": "projects/my-project",
    "db_path": "projects/my-project/data/archaeology.db",
    "analysis_files": [
      "projects/my-project/deliverables/analysis-sdlc-gap-finder.json",
      "projects/my-project/deliverables/analysis-ml-pattern-mapper.json",
      "projects/my-project/deliverables/analysis-agentic-workflow.json",
      "projects/my-project/deliverables/analysis-formal-terms-mapper.json",
      "projects/my-project/deliverables/analysis-source-archaeologist.json",
      "projects/my-project/deliverables/analysis-youtube-correlator.json"
    ]
  }
}
```

#### Status Values

- `complete`: All critical steps succeeded
- `failed`: One or more critical steps failed (init, mine, build-db)
- `error`: Unexpected error occurred
- `running`: Pipeline is still executing (should not appear in final output)

### Integration with research-scout

#### Example Configuration

If research-scout supports webhook or script execution, configure it to call the scout hook:

```yaml
# research-scout config example
on_repo_discovered:
  trigger_archaeology:
    script: "/path/to/devarch-framework/scripts/integrations/scout_hook.py"
    args:
      - "--repo-url"
      - "{{repo_url}}"
      - "--project-name"
      - "{{repo_name}}"
    parse_output: json
    on_success:
      log: "Archaeology analysis complete: {{output.metrics.commit_count}} commits"
    on_failure:
      log: "Archaeology analysis failed: {{output.error}}"
```

#### Programmatic Integration

```python
import json
import subprocess

def analyze_repo(repo_url: str, project_name: str) -> dict:
    """Trigger archaeology analysis from research-scout."""
    cmd = [
        "python3", "scripts/integrations/scout_hook.py",
        "--repo-url", repo_url,
        "--project-name", project_name,
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd="/path/to/devarch-framework",
    )
    return json.loads(result.stdout)

# Usage
result = analyze_repo(
    "https://github.com/user/repo",
    "my-project"
)
if result["status"] == "complete":
    print(f"Analysis complete: {result['metrics']['commit_count']} commits")
else:
    print(f"Analysis failed: {result.get('error')}")
```

### CI/CD Integration

#### GitHub Actions Example

```yaml
name: Archaeology Analysis

on:
  push:
    branches: [main]

jobs:
  archaeology:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout devarch-framework
        uses: actions/checkout@v3
        with:
          path: devarch-framework

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd devarch-framework
          pip install -e .

      - name: Run archaeology analysis
        run: |
          python3 scripts/integrations/scout_hook.py \
            --repo-url ${{ github.repositoryUrl }} \
            --project-name ${{ github.event.repository.name }}

      - name: Upload artifacts
        uses: actions/upload-artifact@v3
        with:
          name: archaeology-results
          path: devarch-framework/projects/*/deliverables/
```

#### GitLab CI Example

```yaml
archaeology:
  script:
    - pip install -e .
    - python3 scripts/integrations/scout_hook.py
        --repo-url $CI_REPOSITORY_URL
        --project-name $CI_PROJECT_NAME
  artifacts:
    paths:
      - projects/*/deliverables/
    reports:
      archaeology: archaeology-report.json
```

### Error Handling

The script handles errors gracefully:

- **Critical failures** (init, mine, build-db): Set `status: failed` and exit with code 1
- **Partial failures** (signals, analyze): Set step status to `partial` but continue
- **Clone failures**: Return error message with details
- **Timeouts**: Each step has a timeout (mine: 10min, build-db: 10min, analyze: 10min)

### Exit Codes

- `0`: Success (complete or partial success)
- `1`: Failure (critical step failed or error occurred)

### Troubleshooting

#### Repository Not Found

```json
{
  "status": "failed",
  "error": "Repository not found: /path/to/repo"
}
```

**Solution**: Verify the repository path or URL is correct.

#### Clone Timeout

```json
{
  "status": "failed",
  "error": "git clone timed out"
}
```

**Solution**: Large repositories may take longer to clone. Consider using a local path or increasing the timeout in the script.

#### Project Already Exists

If a project with the same name exists, the init step will fail. Either:
- Use a unique project name
- Delete the existing project directory first
- Modify the script to update existing projects

### Advanced Usage

#### Batch Processing

```bash
# Analyze multiple repos
while read -r url name; do
  python3 scripts/integrations/scout_hook.py \
    --repo-url "$url" \
    --project-name "$name"
done < repos.txt
```

#### Parallel Processing

```bash
# Analyze repos in parallel (GNU parallel)
cat repos.txt | parallel -j 4 \
  "python3 scripts/integrations/scout_hook.py \
    --repo-url {1} \
    --project-name {2}"
```

#### Custom Analysis Pipeline

To customize the pipeline steps, edit the `run_full_pipeline()` function in `scout_hook.py`:

```python
# Skip signals detection
# success, msg, data = detect_signals(project_name)

# Run specific analysis vectors only
cmd = [sys.executable, "-m", "archaeology.cli", "analyze", project_name, "--vector", "sdlc-gap-finder"]
```

## Contributing

When adding new integration hooks:

1. Follow the same input/output conventions (JSON stdin/stdout)
2. Include comprehensive error handling
3. Document the hook in this README
4. Add examples for common use cases
5. Test with both URLs and local paths

## Support

For issues or questions:
- Open an issue on the devarch-framework repository
- Check the main devarch-framework documentation
- Review the CLI help: `archaeology --help`
