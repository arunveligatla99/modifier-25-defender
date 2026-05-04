# Modifier 25 Defender, top-level developer commands.
# Targets are intentionally thin wrappers around uv / docker compose / npm so
# they remain debuggable. Each target's eventual implementation lands in the
# task identified in tasks.md (T-numbers in comments).

PYTHON   := uv run python
PYTEST   := uv run pytest
RUFF     := uv run ruff
BLACK    := uv run black
MYPY     := uv run mypy
COMPOSE  := docker compose -f infra/docker-compose.yaml

.PHONY: help install corpus synthetic-data eval eval-retrieval eval-defensibility eval-adversarial eval-faithfulness dev replay test test-unit test-integration lint format type check check-emdash check-phi up down logs ui-install ui-dev ui-build clean

help:
	@echo "Modifier 25 Defender developer commands:"
	@echo "  make install            - install Python and Node dependencies"
	@echo "  make corpus             - ingest, chunk, embed, index reference corpus (T120)"
	@echo "  make synthetic-data     - generate 100 synthetic encounters (T108)"
	@echo "  make eval               - run full eval harness (T302)"
	@echo "  make eval-retrieval     - retrieval recall@5 only (T119)"
	@echo "  make eval-defensibility - verdict + per-criterion accuracy only (T129)"
	@echo "  make eval-adversarial   - compliance guard adversarial recall only (T136)"
	@echo "  make eval-faithfulness  - RAGAS faithfulness only (T130)"
	@echo "  make dev                - run backend dev server (uvicorn --reload)"
	@echo "  make ui-dev             - run UI dev server (vite)"
	@echo "  make replay TRACE_ID=X  - re-execute a Langfuse trace against current code"
	@echo "  make test               - all unit + integration tests"
	@echo "  make lint               - ruff check"
	@echo "  make format             - black write"
	@echo "  make type               - mypy strict on app/"
	@echo "  make check              - lint + type + format check + em-dash + phi"
	@echo "  make check-emdash       - run em-dash gate (Constitution CS-3, T011)"
	@echo "  make check-phi          - run PHI denylist gate (Constitution Principle IV, T028)"
	@echo "  make up                 - docker compose up -d"
	@echo "  make down               - docker compose down"
	@echo "  make logs               - docker compose logs -f"
	@echo "  make clean              - remove caches and __pycache__"

install:
	uv sync --extra dev
	cd ui && npm install

# ----- Corpus and data -----

corpus:
	$(PYTHON) -m app.retrieval.cli build-corpus

synthetic-data:
	$(PYTHON) -m eval.synthetic.cli generate --seed 42 --count 100

# ----- Eval harness -----

eval:
	$(PYTHON) -m eval.run

eval-retrieval:
	$(PYTHON) -m eval.retrieval.recall_at_5

eval-defensibility:
	$(PYTHON) -m eval.defensibility.accuracy

eval-adversarial:
	$(PYTHON) -m eval.adversarial.recall

eval-faithfulness:
	$(PYTHON) -m eval.faithfulness.ragas_runner

# ----- Backend dev -----

dev:
	uv run uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000

replay:
	@if [ -z "$(TRACE_ID)" ]; then echo "TRACE_ID is required: make replay TRACE_ID=lf_t_..."; exit 2; fi
	$(PYTHON) -m app.observability.replay --trace-id $(TRACE_ID)

# ----- UI dev -----

ui-install:
	cd ui && npm install

ui-dev:
	cd ui && npm run dev

ui-build:
	cd ui && npm run build

# ----- Tests and quality gates -----

test:
	$(PYTEST)

test-unit:
	$(PYTEST) tests/unit -v

test-integration:
	$(PYTEST) tests/integration -m integration -v

lint:
	$(RUFF) check app eval tests scripts

format:
	$(BLACK) app eval tests scripts

type:
	$(MYPY)

check: lint type
	$(BLACK) --check app eval tests scripts
	$(MAKE) check-emdash
	$(MAKE) check-phi

check-emdash:
	$(PYTHON) scripts/check_emdash.py

check-phi:
	$(PYTHON) scripts/check_phi.py

# ----- Docker compose -----

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

# ----- Clean -----

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
