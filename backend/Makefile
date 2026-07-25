.PHONY: install run dev test lint clean build deploy

# Install dependencies
install:
	pip install -r requirements.txt

# Run development server
run:
	python run.py

# Run with auto-reload
dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# Run tests
test:
	pytest tests/ -v --cov=app --cov-report=term-missing

# Run linter
lint:
	ruff check app/
	ruff format --check app/

# Format code
format:
	ruff format app/

# Clean build artifacts
clean:
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf dist
	rm -rf *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Build for Lambda deployment
build:
	mkdir -p dist
	pip install -r requirements.txt -t dist/
	cp -r app dist/
	cp lambda_handler.py dist/
	cd dist && zip -r ../function.zip .

# Deploy to AWS (requires Terraform)
deploy: build
	cd ../infrastructure && terraform apply -auto-approve

# Create virtual environment
venv:
	python -m venv venv
	@echo "Run 'source venv/bin/activate' to activate"

# Database migrations (if using Alembic)
migrate:
	alembic upgrade head

# Generate migration
migration:
	alembic revision --autogenerate -m "$(msg)"

# Health check
health:
	curl -s http://localhost:8080/health | python -m json.tool
