"""CI runs the repository's own check on every pull request and push to main (a failing
`make test` once reached main because the only check was local)."""

from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


def test_the_workflow_exists() -> None:
    assert WORKFLOW.is_file()


def test_it_runs_on_pull_requests_and_pushes_to_main() -> None:
    text = WORKFLOW.read_text()
    assert "pull_request" in text
    assert "push" in text and "main" in text


def test_it_runs_the_repository_check() -> None:
    text = WORKFLOW.read_text()
    assert "make lint" in text
    assert "make test" in text
    assert "uv sync" in text


def test_it_needs_no_secrets_and_runs_no_benchmark() -> None:
    text = WORKFLOW.read_text()
    assert "secrets." not in text
    for forbidden in ("paired_run", "run_canary", "guard_bench", "GEMINI_API_KEY"):
        assert forbidden not in text, forbidden
