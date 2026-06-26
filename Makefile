# Convenience targets for local development. The API service keeps its
# virtualenv in api/.venv (gitignored).

.PHONY: help api-venv api-test api-lint detector-test up down logs

help:
	@echo "Targets:"
	@echo "  api-venv      Create api/.venv and install runtime + dev deps"
	@echo "  api-test      Run the FastAPI backend test suite"
	@echo "  api-lint      Run ruff over api/ and detector/"
	@echo "  detector-test Run the detector violation-rules unit tests"
	@echo "  up            docker compose up --build (full stack)"
	@echo "  down          docker compose down"
	@echo "  logs          Tail docker compose logs"

api-venv:
	cd api && python3 -m venv .venv && \
		./.venv/bin/pip install --upgrade pip && \
		./.venv/bin/pip install -r requirements.txt -r requirements-dev.txt

api-test:
	cd api && ./.venv/bin/python -m pytest -q

api-lint:
	cd api && ./.venv/bin/ruff check . ../detector

detector-test:
	cd detector && python3 -m pytest -q

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f
