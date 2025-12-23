.PHONY: help build run stop logs test clean certs

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

certs: ## Generate test certificates
	python -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt
	. .venv/bin/activate && python -m tsa.cert_utils --dir certs

build: ## Build Docker image
	docker build -t tsa-server:latest .

run: ## Run Docker container
	docker-compose up -d

stop: ## Stop Docker container
	docker-compose down

logs: ## Show container logs
	docker-compose logs -f

test: ## Test the running container
	@echo "Testing health endpoint..."
	@curl -sS http://localhost:5000/health | python -m json.tool
	@echo "\nTesting timestamp endpoint (DER)..."
	@curl -sS -X POST http://localhost:5000/tsa --data-binary "test" -o test.tsr
	@. .venv/bin/activate && python tools/verify_tsr.py test.tsr certs/tsa_cert.pem
	@echo "\nTesting timestamp endpoint (JSON)..."
	@curl -sS -X POST "http://localhost:5000/tsa?format=json" --data-binary "test" | python -m json.tool | head -n 10

clean: ## Remove containers and test files
	docker-compose down
	docker rmi tsa-server:latest 2>/dev/null || true
	rm -f test.tsr docker-test.tsr reply*.der reply*.tsr

restart: stop run ## Restart the container

shell: ## Open shell in running container
	docker exec -it $$(docker-compose ps -q tsa-server) sh

verify: ## Verify a timestamp reply (usage: make verify FILE=timestamp.tsr)
	@. .venv/bin/activate && python tools/verify_tsr.py $(FILE) certs/tsa_cert.pem

# Testing targets
test-local: ## Run all tests locally (like GitHub Actions)
	@bash run_tests.sh

test-unit: ## Run unit tests only
	@. .venv/bin/activate && pip install -q -r requirements-dev.txt
	@. .venv/bin/activate && pytest tests/ -v

test-coverage: ## Run tests with coverage report
	@. .venv/bin/activate && pip install -q -r requirements-dev.txt
	@. .venv/bin/activate && pytest tests/ --cov=tsa --cov-report=html --cov-report=term
	@echo "\nCoverage report: htmlcov/index.html"

test-lint: ## Run linting checks
	@. .venv/bin/activate && pip install -q -r requirements-dev.txt
	@echo "Running flake8..."
	@. .venv/bin/activate && flake8 tsa/ tools/ client/ tests/
	@echo "Running black check..."
	@. .venv/bin/activate && black --check tsa/ tools/ client/ tests/
	@echo "Running isort check..."
	@. .venv/bin/activate && isort --check-only tsa/ tools/ client/ tests/

format: ## Auto-format code with black and isort
	@. .venv/bin/activate && pip install -q -r requirements-dev.txt
	@echo "Formatting with black..."
	@. .venv/bin/activate && black tsa/ tools/ client/ tests/
	@echo "Sorting imports with isort..."
	@. .venv/bin/activate && isort tsa/ tools/ client/ tests/
