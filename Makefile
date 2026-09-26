.PHONY: sync test parity integration lint clean-docker clean

sync:
	uv sync

test:
	uv run pytest -q tests/

parity:
	uv run pytest -q tests/test_differential.py

# Integration tests that drive a real Docker daemon. These are where most harness
# defects have been found; the unit suite passed throughout.
integration:
	uv run pytest -q tests/test_docker_integration.py

lint:
	uv run ruff check lab tests scripts
	uv run pyright

clean-docker:
	python3 -c "import shutil, subprocess; print(f'Free disk: {shutil.disk_usage(\"/\").free / (1024**3):.1f} GB'); subprocess.run(['docker', 'system', 'prune', '-f']); subprocess.run(['docker', 'volume', 'prune', '-f'])"

clean:
	rm -rf .pytest_cache/ htmlcov/ .coverage
