.PHONY: run migrate revision reset-db test lint format typecheck check clean metrics glossary-mine seed-glossary

run:
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Alembic owns the schema (ADR-06). The application no longer creates tables at
# startup, so a fresh checkout needs this before `make run`.
migrate:
	alembic upgrade head

# Write a migration from whatever changed in src/database/models.py, then read
# it: autogenerate is a draft, not an answer.
revision:
	alembic revision --autogenerate -m "$(m)"

# Drops every table and rebuilds it from the migrations, then seeds the two dev
# accounts. Destroys the local data on purpose; production is upgraded with
# `make migrate` instead, which keeps it.
reset-db:
	alembic downgrade base
	alembic upgrade head
	python scripts/seed_dev_users.py

test:
	pytest tests/ -v

# Summarises what the agent actually did, from the database. Calls no model and
# costs no quota, unlike `python eval/run_eval.py` which scores translation
# quality against the golden set.
metrics:
	python scripts/report_metrics.py

# Proposes glossary entries from corrections several people made the same way.
# Costs quota: one model call per surviving cluster, so run it deliberately
# rather than on every push. `--no-write` prints what it would create.
glossary-mine:
	python scripts/mine_glossary.py --since 7d

# Loads the curated starter glossary. Safe to run repeatedly: entries are
# matched on the key the database is unique on and updated in place, so editing
# seed/glossary_en_vi.jsonl and re-running is how to change it in development.
seed-glossary:
	python scripts/seed_glossary.py

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
