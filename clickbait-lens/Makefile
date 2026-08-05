.PHONY: install test backend extension e2e lint serve

install:
	cd backend && uv sync --group dev
	cd extension && npm install
	cd e2e && npm install

backend:
	cd backend && uv run pytest -q

extension:
	cd extension && npm run typecheck

e2e:
	cd e2e && npm test

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .

test: lint backend extension e2e

serve:
	cd backend && uv run clickbait-lens
