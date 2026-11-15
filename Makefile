.DEFAULT_GOAL := help
.PHONY: help welcome pipeline ingest validate prepare train evaluate register predict monitor serve predict-api ui test lint format clean

PY      := python
DATASET ?=
ARGS    := $(if $(DATASET),--dataset $(DATASET),)
MODEL    = $(shell $(PY) -m pipeline model-name $(ARGS))

help: ## Show this help
	@grep -hE '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36mmake %-12s\033[0m %s\n", $$1, $$2}'
	@echo "  Add DATASET=f1 or DATASET=spl to override team.yaml."

welcome: ## Printed when the Codespace opens
	@echo ""
	@echo "  MLOps course - $$(grep '^team:' team.yaml | awk '{print $$2}') on $$(grep '^dataset:' team.yaml | awk '{print $$2}')"
	@echo "  MLflow UI : $$($(PY) -m pipeline ui)   (PORTS tab, port 5000)"
	@echo "  Start     : make pipeline"
	@echo ""
	@$(MAKE) --no-print-directory help

pipeline: ## Run every stage as one MLflow parent run
	$(PY) -m pipeline all $(ARGS)

ingest validate prepare train evaluate register predict monitor: ## Run one stage, e.g. make train
	$(PY) -m pipeline $@ $(ARGS)

serve: ## Serve the @champion model as a REST API on port 5001
	mlflow models serve -m "models:/$(MODEL)@champion" --host 0.0.0.0 --port 5001 --env-manager local

predict-api: ## Score the 2026 season through the running API (run make serve in another terminal)
	$(PY) -m pipeline predict --endpoint http://localhost:5001/invocations $(ARGS)

ui: ## Print the MLflow UI address
	@$(PY) -m pipeline ui

test: ## Run the tests
	$(PY) -m pytest

lint: ## Check code style
	ruff check .
	ruff format --check .

format: ## Fix code style
	ruff check --fix .
	ruff format .

clean: ## Delete local pipeline outputs (MLflow data in .mlflow/ is kept)
	rm -rf work reports .pytest_cache .ruff_cache
