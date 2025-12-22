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
