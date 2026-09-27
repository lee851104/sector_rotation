.PHONY: setup data smoke test build serve
setup:
	uv sync --locked
	npm ci
smoke:
	uv run python -m gics.serving.pipeline --smoke
data:
	uv run python -m gics.serving.pipeline
test:
	uv run pytest -q
	npm test
build:
	npm run build
serve:
	npm run dev
