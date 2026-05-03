# Contributing to DevArch Framework

Thank you for your interest in contributing to DevArch! This document provides guidelines for contributing to the project.

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Git
- Virtual environment (recommended)

### Installation

```bash
# Clone the repository
git clone https://github.com/Pastorsimon1798/devarch-framework.git
cd devarch-framework

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode with development dependencies
pip install -e ".[dev]"

# Verify installation
devarch --help
pytest --version
```

## Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_audit.py

# Run with coverage
pytest --cov=archaeology --cov-report=html

# Run with verbose output
pytest -v
```

## Code Style

This project follows Python best practices:

- **PEP 8** for code formatting
- **Type hints** for function signatures
- **Docstrings** for public functions and classes
- **Meaningful names** for variables and functions

### Code Formatting

While we don't enforce strict formatting rules, please keep code readable:

- Use 4 spaces for indentation
- Limit lines to 100 characters where practical
- Add docstrings to functions that do something non-obvious
- Use type hints for function parameters and returns

## Adding Analysis Vectors

Analysis vectors are modular analysis plugins. To add a new one:

1. **Create the vector directory** in `analysis-vectors/`:
   ```
   analysis-vectors/my-vector/
   ├── README.md
   ├── vector.md
   └── output/
   ```

2. **Define the vector** in `vector.md`:
   ```markdown
   # My Analysis Vector

   ## Purpose
   What this vector analyzes and why it matters.

   ## Input
   - Required data sources
   - Parameters

   ## Analysis
   Step-by-step analysis process.

   ## Output
   Expected findings and format.
   ```

3. **Register the vector** in the analysis runner (if automated):
   - Add vector name to `archaeology/analysis_runner.py`
   - Implement the analysis logic

4. **Test the vector**:
   ```bash
   devarch analyze test-project --vector my-vector
   ```

## Reporting Issues

### Bug Reports

When reporting bugs, please include:

1. **Python version**: `python --version`
2. **DevArch version**: `devarch --version`
3. **Steps to reproduce**: Minimal reproduction case
4. **Expected behavior**: What you expected to happen
5. **Actual behavior**: What actually happened
6. **Error messages**: Full traceback if applicable
7. **Environment**: OS and other relevant details

### Feature Requests

For feature requests, please describe:

1. **Use case**: What problem would this solve?
2. **Proposed solution**: How do you envision it working?
3. **Alternatives**: What alternatives have you considered?
4. **Impact**: Who would benefit and how?

## Pull Request Process

1. **Fork the repository** and create a branch from `main`
2. **Make your changes** following code style guidelines
3. **Add tests** for new functionality
4. **Update documentation** if needed
5. **Run tests** to ensure nothing breaks
6. **Submit a pull request** with:
   - Clear description of changes
   - Reference to related issues
   - Screenshots for UI changes (if applicable)

### PR Checklist

- [ ] Tests pass locally
- [ ] New tests added for new features
- [ ] Documentation updated
- [ ] Commit messages are clear and descriptive
- [ ] No unrelated changes included

## Development Workflow

### Making Changes

1. Start with a clear goal in mind
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make incremental commits with clear messages
4. Test frequently
5. Refactor before submitting

### Testing Your Changes

```bash
# Run the demo to verify basic functionality
devarch demo --force --build-db

# Run tests
pytest

# Manual testing with a real repo
devarch init test-project --repo-url https://github.com/user/repo
devarch mine /path/to/repo --project test-project
devarch build-db test-project
devarch signals test-project
devarch analyze test-project
```

## Project Structure

Understanding the codebase helps with contributions:

```
archaeology/          # Main package
  cli.py              # CLI entry point (all commands)
  analysis_runner.py  # Vector orchestration
  audit.py            # Validation and auditing
  era_scanner.py      # Era detection logic
  era_cascade.py      # Era label propagation
  report.py           # Report generation
  db/                 # Database operations
  classifiers/        # Signal classification
  extractors/         # Data extraction
  validators/         # Output validation
  visualization/      # HTML generation

analysis-vectors/     # Vector definitions
config/               # Configuration schemas
tests/                # Test suite
```

## Questions?

- Check the main [README.md](README.md) for usage documentation
- Review [CONTEXT.md](CONTEXT.md) for architecture details
- Open an issue for bugs or feature requests
- Join discussions in existing issues

Thank you for contributing to DevArch!
