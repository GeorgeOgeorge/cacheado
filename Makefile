.PHONY: test test-unit test-integration test-coverage test-verbose clean install-test-deps

# Install dependencies
install-deps:
	pip install -r requirements.txt

# Run all tests
test:
	python -m pytest

# Run only unit tests
test-unit:
	python -m pytest tests/test_cache.py tests/test_storage_in_memory.py tests/test_eviction_lru.py tests/test_policy_manager.py tests/test_scope_config.py tests/test_cache_types.py -v

# Run only integration tests
test-integration:
	python -m pytest tests/test_integration.py -v

# Run tests with coverage
test-coverage:
	python -m pytest --cov=. --cov-report=html --cov-report=term-missing --cov-report=xml

# Run tests with verbose output
test-verbose:
	python -m pytest -v -s

# Run specific test file
test-file:
	python -m pytest $(FILE) -v

# Run tests matching pattern
test-pattern:
	python -m pytest -k $(PATTERN) -v

# Clean test artifacts
clean:
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Run tests and generate coverage report
check-all: clean test-coverage

# Quick test run (no coverage)
quick-test:
	python -m pytest --tb=line -q

# Test with specific Python version
test-python:
	python$(VERSION) -m pytest

# Run performance tests (if any)
test-performance:
	python -m pytest -m "not slow" --durations=10

# Install test dependencies (alias)
install-test-deps: install-deps

# Install quality dependencies (alias)
install-quality-deps: install-deps

lint:
	flake8 .

format:
	black .
	isort .

format-check:
	black --check --diff .
	isort --check-only --diff .

type-check:
	@output=$$(mypy . --ignore-missing-imports 2>&1); \
	if echo "$$output" | grep -q "error:"; then \
		echo "$$output" | grep "error:"; \
		echo "$$output" | grep "Found.*error"; \
	else \
		echo "MyPy: No errors found"; \
	fi

quality-check: lint format-check type-check

# Help
help:
	@echo "Available targets:"
	@echo "  install-test-deps    - Install test dependencies"
	@echo "  install-quality-deps - Install code quality dependencies"
	@echo "  test                - Run all tests"
	@echo "  test-unit           - Run unit tests only"
	@echo "  test-integration    - Run integration tests only"
	@echo "  test-coverage       - Run tests with coverage report"
	@echo "  test-verbose        - Run tests with verbose output"
	@echo "  test-file FILE=     - Run specific test file"
	@echo "  test-pattern PATTERN= - Run tests matching pattern"
	@echo "  lint                - Run linting with flake8"
	@echo "  format              - Format code with black and isort"
	@echo "  format-check        - Check code formatting"
	@echo "  type-check          - Run type checking with mypy"
	@echo "  quality-check       - Run all quality checks"
	@echo "  clean               - Clean test artifacts"
	@echo "  check-all           - Run all tests with coverage"
	@echo "  quick-test          - Quick test run without coverage"
	@echo "  help                - Show this help message"
