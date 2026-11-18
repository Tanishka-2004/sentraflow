# SentraFlow Project Orchestration Makefile

.PHONY: help up down seed pipeline test audit lint demo clean

help:
	@echo "SentraFlow Governed Financial Lakehouse Commands:"
	@echo "  make up       - Start local MinIO, Postgres, Kafka, and Redis containers"
	@echo "  make down     - Stop all local containers"
	@echo "  make seed     - Generate synthetic banking transactions & customers"
	@echo "  make pipeline - Execute end-to-end Medallion pipeline (Bronze -> Silver -> Gold)"
	@echo "  make test     - Run complete unit and integration test suite (pytest)"
	@echo "  make audit    - Run live end-to-end integration & UI route verification"
	@echo "  make lint     - Run ruff, black formatting check, and mypy static analysis"
	@echo "  make demo     - Full quickstart: pipeline execution, test suite, and launch info"

up:
	docker compose up -d

down:
	docker compose down

seed:
	python -m data_generator.cli --customers 2000 --txns 20000 --landing-dir landing/

pipeline:
	python scripts/run_medallion_pipeline.py

test:
	python -m pytest tests/ -v

audit:
	python scripts/verify_platform_live.py

lint:
	ruff check .
	black --check .

demo: pipeline test
	@echo "Demo ready! Launch API with: uvicorn api.main:app --reload --port 8000"
	@echo "Launch Dashboard with: cd dashboard && npm run dev"

clean:
	rm -rf .pytest_cache .ruff_cache landing/ *.db

