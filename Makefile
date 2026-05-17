run:
	uv run python main.py

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run ty check .

check: lint typecheck
