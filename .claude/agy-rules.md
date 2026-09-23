Repo rules (superstate-eval):
- NEVER start a benchmark or paid run: no scripts/paired_run.py, run_canary.sh, run_exp*.sh, guard_bench.py or any command that calls a model API or launches task containers. Tests use stub binaries only.
- Do NOT prune or remove Docker containers, images or volumes (no `make clean-docker`, no `docker system prune`).
- Do NOT edit FINDINGS.md, EXPERIMENTS.md or anything under results/.
- Use `uv run` for Python. In a fresh worktree run `uv sync` first.
- Before committing, run: make lint && make test. Report the results.
