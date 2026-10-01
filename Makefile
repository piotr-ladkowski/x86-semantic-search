# Run `make help` for the list. Everything goes through uv (Python) and npm (Tailwind only).
IMAGE ?= docx86
TAG   ?= 0.1.0

.DEFAULT_GOAL := help
.PHONY: help setup css index validate progress test eval lint fmt check dev image

help: ## Show this help
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

setup: ## Install Python and Node dependencies
	uv sync
	npm ci

css: ## Build Tailwind CSS -> src/docx86/static/app.css
	npm run build:css

index: ## Embed content/ and write the search index to index/
	uv run docx86 build-index

validate: ## Validate content/ (schema, cross-references, roster)
	uv run docx86 validate

progress: ## Regenerate the README progress block and content/README.md
	uv run docx86 progress

test: ## Run the test suite (no model download needed)
	uv run pytest

eval: index ## Search-quality check with the real model (downloads it once)
	uv run docx86 eval

lint: ## Ruff lint + format check
	uv run ruff check .
	uv run ruff format --check .

fmt: ## Auto-fix lint issues and format
	uv run ruff check --fix .
	uv run ruff format .

check: lint test validate ## Everything CI would run; do this before committing
	uv run docx86 progress --check

dev: css ## Dev server on :8000 with reload (rebuilds a stale index on start)
	DOCX86_REBUILD_STALE_INDEX=1 uv run uvicorn docx86.main:create_app --factory --reload \
		--reload-dir src --reload-dir content \
		--reload-include '*.md' --reload-include '*.yaml' --reload-include '*.html'

image: ## Build the container image: make image IMAGE=registry/name TAG=1.2.3
	docker build -t $(IMAGE):$(TAG) .
