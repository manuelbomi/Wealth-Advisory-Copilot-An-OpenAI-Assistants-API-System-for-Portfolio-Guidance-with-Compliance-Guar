.PHONY: install test lint typecheck run docker-build docker-run fmt

install:
	python -m pip install --upgrade pip
	pip install -r requirements-dev.txt

test:
	pytest -v

lint:
	ruff check .

fmt:
	ruff format .

typecheck:
	mypy app

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

docker-build:
	docker build -t wealth-advisory-copilot:local .

docker-run:
	docker run --rm -p 8000:8000 --env-file .env wealth-advisory-copilot:local
