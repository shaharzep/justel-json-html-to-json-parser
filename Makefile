# Makefile for Juportal Decisions Parser

# Variables
PYTHON := python3
PIP := pip3
PYTEST := pytest
COVERAGE := coverage

# Directories
SRC_DIR := src
TEST_DIR := tests
UTILS_DIR := juportal_utils
OUTPUT_DIR := output

# Default target
.DEFAULT_GOAL := help

# Help target
help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Installation
install: ## Install dependencies
	$(PIP) install -r requirements.txt
	$(PIP) install pytest pytest-cov

# Testing targets
test: ## Run all tests
	$(PYTEST) $(TEST_DIR) -v

test-unit: ## Run unit tests only
	$(PYTEST) $(TEST_DIR)/unit -v -m "unit"

test-integration: ## Run integration tests only
	$(PYTEST) $(TEST_DIR)/integration -v -m "integration"

test-field: ## Run field extraction tests
	$(PYTEST) $(TEST_DIR)/unit/test_field_extraction.py -v

test-text: ## Run text processing tests
	$(PYTEST) $(TEST_DIR)/unit/test_text_processing.py -v

test-notices: ## Run notices extraction tests
	$(PYTEST) $(TEST_DIR)/unit/test_notices.py -v

test-full: ## Run full transformation tests
	$(PYTEST) $(TEST_DIR)/integration/test_full_transformation.py -v

# Coverage targets
coverage: ## Run tests with coverage
	$(COVERAGE) run -m pytest $(TEST_DIR)
	$(COVERAGE) report
	$(COVERAGE) html

coverage-report: ## Generate HTML coverage report
	$(COVERAGE) html
	@echo "Coverage report generated in htmlcov/index.html"

# Code quality
lint: ## Run linting
	$(PYTHON) -m flake8 $(SRC_DIR) $(UTILS_DIR) --max-line-length=120

format: ## Format code with black
	$(PYTHON) -m black $(SRC_DIR) $(UTILS_DIR) $(TEST_DIR)

typecheck: ## Run type checking with mypy
	$(PYTHON) -m mypy $(SRC_DIR) $(UTILS_DIR)

# Transformation targets
transform: ## Run transformation on raw JSONs
	$(PYTHON) -m juportal_utils.transform_juportal --input raw_jsons --output $(OUTPUT_DIR)

transform-verbose: ## Run transformation with verbose output
	$(PYTHON) -m juportal_utils.transform_juportal --input raw_jsons --output $(OUTPUT_DIR) --verbose

# Utility targets
extract-keywords: ## Extract keywords to CSV
	$(PYTHON) extract_keywords.py

upload-s3: ## Upload valid files to S3
	$(PYTHON) upload_valid_to_s3_zipped.py

sync-s3: ## Sync files from S3
	$(PYTHON) src/sync_s3_jsons.py

# Cleaning
clean: ## Clean generated files
	rm -rf $(OUTPUT_DIR)/*.json
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf **/__pycache__/
	rm -rf *.pyc

clean-output: ## Clean only output directory
	rm -rf $(OUTPUT_DIR)/*.json

# Development
dev-install: ## Install development dependencies
	$(PIP) install -r requirements.txt
	$(PIP) install pytest pytest-cov pytest-mock
	$(PIP) install black flake8 mypy
	$(PIP) install ipython ipdb

watch-test: ## Run tests in watch mode
	$(PYTEST) $(TEST_DIR) -v --watch

# CI/CD
ci-test: ## Run tests for CI
	$(PYTEST) $(TEST_DIR) -v --cov --cov-report=xml --junitxml=test-results.xml

.PHONY: help install test test-unit test-integration test-field test-text test-notices test-full \
        coverage coverage-report lint format typecheck transform transform-verbose \
        extract-keywords upload-s3 sync-s3 clean clean-output dev-install watch-test ci-test