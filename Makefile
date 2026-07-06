.PHONY: install format lint test docker-up docker-build migrate run-valid run-price-failure

install:
	pip install -e ".[dev]"

format:
	black backend investigator

lint:
	ruff check backend investigator
	mypy backend investigator

test:
	pytest backend/tests

migrate:
	alembic upgrade head

docker-up:
	docker compose up --build

docker-build:
	docker compose build

run-valid:
	python -m investigator run --pipeline daily_order_analytics --input sample_data/valid/orders.csv

run-price-failure:
	python -m investigator run --pipeline daily_order_analytics --input sample_data/failures/price_type_change.csv

