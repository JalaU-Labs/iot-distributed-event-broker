.PHONY: help up down logs test test-integration test-all lint format typecheck check pre-commit install asyncapi-validate asyncapi-docs pages-build clean
help:
	@echo "Available commands:"
	@echo "  make up               - Start Docker Compose services"
	@echo "  make down             - Stop Docker Compose services"
	@echo "  make logs             - Show Docker Compose logs"
	@echo "  make test             - Run unit tests with coverage"
	@echo "  make test-integration - Run integration tests (requires broker)"
	@echo "  make test-all         - Run all tests without coverage"
	@echo "  make lint             - Run ruff and mypy"
	@echo "  make format           - Format code with ruff"
	@echo "  make typecheck        - Run mypy"
	@echo "  make check            - Run format check, lint, types and tests"
	@echo "  make pre-commit       - Run pre-commit hooks"
	@echo "  make install          - Install pre-commit hooks"
	@echo "  make clean            - Remove caches"
	@echo "  make asyncapi-validate - Validate the AsyncAPI specification"
	@echo "  make asyncapi-docs     - Generate HTML documentation for the AsyncAPI spec"
	@echo "  make pages-build       - Build the GitHub Pages site locally"

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

test:
	uv run pytest

test-integration:
	uv run pytest -m integration --no-cov

test-all:
	uv run pytest -m "" --no-cov

lint:
	uv run ruff check .
	uv run mypy src tests

format:
	uv run ruff format .

typecheck:
	uv run mypy src tests

check:
	uv run ruff format --check .
	uv run ruff check .
	uv run mypy src tests
	uv run pytest

pre-commit:
	uv run pre-commit run --all-files

install:
	uv run pre-commit install

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage

asyncapi-validate:
	uv run pytest tests/unit/test_asyncapi_spec.py -v --no-cov

asyncapi-docs:
	@command -v npx >/dev/null 2>&1 || { echo "npx not found. Install Node.js to generate AsyncAPI docs."; exit 1; }
	@mkdir -p docs/api
	npx --yes @asyncapi/cli@latest generate fromTemplate asyncapi.yaml @asyncapi/html-template@latest -o docs/api --force-write
	@echo "Documentation generated at docs/api/index.html"

pages-build:
	@command -v npx >/dev/null 2>&1 || { echo "npx not found. Install Node.js."; exit 1; }
	@rm -rf dist
	@mkdir -p dist/api
	npx --yes @asyncapi/cli@3 generate fromTemplate asyncapi.yaml @asyncapi/html-template -o dist/api --force-write
	@cp docs/pages/index.html dist/index.html
	@echo "Built at dist/. Open dist/index.html in a browser to preview."