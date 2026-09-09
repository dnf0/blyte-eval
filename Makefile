.PHONY: sync test parity clean-docker clean

sync:
	uv sync

test:
	uv run pytest -q tests/

parity:
	uv run pytest -q tests/test_differential.py

clean-docker:
	python3 -c "import shutil, subprocess; print(f'Free disk: {shutil.disk_usage(\"/\").free / (1024**3):.1f} GB'); subprocess.run(['docker', 'system', 'prune', '-f']); subprocess.run(['docker', 'volume', 'prune', '-f'])"

clean:
	rm -rf .pytest_cache/ htmlcov/ .coverage
