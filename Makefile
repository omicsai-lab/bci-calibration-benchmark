.PHONY: install test lint smoke prepare-pilot run-pilot aggregate-pilot figures-pilot clean

install:
	python -m pip install -e '.[dev]'

test:
	pytest

lint:
	ruff check .

smoke:
	python scripts/run_smoke_test.py

prepare-pilot:
	python scripts/prepare_data.py --config configs/pilot.yaml

run-pilot:
	python scripts/run_benchmark.py --config configs/pilot.yaml

aggregate-pilot:
	python scripts/aggregate_results.py --config configs/pilot.yaml

figures-pilot:
	python scripts/make_figures.py --config configs/pilot.yaml

clean:
	rm -rf build dist .pytest_cache .ruff_cache .mypy_cache htmlcov
