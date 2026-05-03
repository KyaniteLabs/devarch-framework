.PHONY: help install install-dev test demo lint clean validate serve

help:  ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install:  ## Install the package
	pip install -e .

install-dev:  ## Install the package with development dependencies
	pip install -e ".[dev]"

test:  ## Run tests
	pytest -v

test-cov:  ## Run tests with coverage
	pytest --cov=archaeology --cov-report=html --cov-report=term

demo:  ## Create and run demo project
	devarch demo --force --build-db

lint:  ## Run basic Python linting
	python3 -m py_compile archaeology/*.py
	python3 -m py_compile archaeology/**/*.py
	@echo "Syntax check passed"

validate:  ## Validate project configuration
	devarch demo --force
	devarch validate demo-project

serve:  ## Start Datasette server for demo project
	devarch serve demo-project --port 8001

clean:  ## Remove build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.db-shm" -delete
	find . -type f -name "*.db-wal" -delete
	@echo "Cleaned build artifacts"

clean-demo:  ## Remove demo project
	rm -rf projects/demo-project
	@echo "Removed demo project"

reset: clean clean-demo  ## Full reset (clean + remove demo)
	@echo "Full reset complete"
