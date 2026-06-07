.PHONY: up down build logs ps clean help

## Default target
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Build images and start all services in the background
	docker compose up --build -d

down: ## Stop and remove containers (volumes are preserved)
	docker compose down

build: ## Build / rebuild all Docker images
	docker compose build

logs: ## Tail logs from all services (Ctrl-C to stop)
	docker compose logs -f

ps: ## Show status of running services
	docker compose ps

clean: ## Stop services and remove volumes (destructive!)
	docker compose down -v
