# WorldBench developer tasks.
#
# Usage: make <target>. Run `make help` to list targets.

PYTHON ?= python
PACKAGE := benchmark

.DEFAULT_GOAL := help

.PHONY: help install dev test lint schema docker-build clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install the package (runtime only)
	$(PYTHON) -m pip install -e .

dev: ## Install the package with the dev toolchain
	$(PYTHON) -m pip install -e '.[dev]'

test: ## Run the test suite
	$(PYTHON) -m pytest

lint: ## Lint and type-check
	$(PYTHON) -m ruff check $(PACKAGE) tests
	$(PYTHON) -m mypy $(PACKAGE)

schema: ## Regenerate the versioned JSON Schema from the models
	$(PYTHON) -m benchmark.schemas.export_schema

docker-build: ## Build the Docker image
	docker build -t worldbench:latest .

clean: ## Remove caches and build artifacts
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
