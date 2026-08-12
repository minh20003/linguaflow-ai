.PHONY: run reset-db test lint format typecheck check clean

run:
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# create_all adds missing tables but never alters existing ones, so a schema
# change is applied in development by recreating the database (ADR-06).
reset-db:
	rm -f data/app.db data/app.db-wal data/app.db-shm
	mkdir -p data
	python scripts/seed_dev_users.py

test:
	pytest tests/ -v

lint:
	ruff check src/ tests/ eval/

format:
	ruff format src/ tests/ eval/

typecheck:
	mypy src/

check: lint format test

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
