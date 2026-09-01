.PHONY: run migrate revision reset-db test lint format typecheck check clean metrics

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

# --- Assistant Agent evaluation (ADR-37, ADR-38) ---------------------------

# Rebuilds the corpus from `eval/assistant/corpus_spec.py`. The JSONL files it
# writes are committed, so this is run when the scenarios change, not before
# every measurement — a corpus that shifts between runs turns a comparison of
# chunking strategies into a comparison of datasets.
assistant-corpus:
	python eval/build_assistant_corpus.py

# Which chunking strategy actually finds the messages that hold the answer.
# COSTS QUOTA: every chunk of every strategy is embedded, which for tier XL is
# roughly ten thousand calls against a Gemini free tier of twenty a day. Use
# `--embedding local:...` above tier M, or `--offline` to check the harness
# rather than a model. Seeds rows into the database; run `assistant-clean` after.
assistant-sweep:
	python eval/assistant_chunk_sweep.py --tier M

# Builds the assistant's chunk index for conversations that predate it. The
# message path keeps new conversations current by itself; this is for history,
# and for the periodic full rebuild that removes the seams the incremental pass
# leaves. COSTS QUOTA: one embedding call per chunk. Start with --dry-run.
assistant-backfill:
	python scripts/backfill_assistant_chunks.py --resume

# What the assistant actually answers, end to end: coverage of the facts the
# corpus planted, faithfulness scored by a judge on a different provider, and
# whether it declines the questions the conversation does not answer. COSTS
# QUOTA: roughly five model calls per question. Start with --limit.
assistant-eval:
	python eval/run_assistant_eval.py --tier S --limit 4

# Removes every conversation and account the corpus builder has seeded. Run it
# after a sweep, and after any run that died partway.
assistant-clean:
	python eval/build_assistant_corpus.py --cleanup

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
