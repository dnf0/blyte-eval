# Native AST Symbol Inspection & Deterministic Context Bounding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Choose an execution mode:
> 1. `superpowers:subagent-driven-development` (recommended for multi-agent reviews, backed by `SKILL.state` / `.agent-state/state.json`)
> 2. `agent-rules:stateful-execution` (SKILL.state) (recommended for deterministic single-agent linear execution)
> 3. `superpowers:executing-plans` (batch execution with manual checkpoints)
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement native AST symbol inspection and line-slicing via `superstate-syntax` and expose the `superstate inspect` CLI tool, eliminating raw file dumps while strictly adhering to the Zero Prompt Engineering invariant.

**Architecture:** Extend `superstate-syntax` with language detection, symbol source slicing, and compact outline formatting using existing Tree-sitter parsers. Expose `superstate inspect` in `superstate-cli` with `--symbol`, `--outline`, `--lines`, and `--json` flags. Reinstall static release binary to host and container, maintaining strict arm input parity.

**Tech Stack:** Rust (edition 2021), Tree-sitter 0.25 (Python, Rust, TypeScript, Go), Clap 4.5, Serde / Serde JSON.

## Global Constraints
- **Zero Prompt Engineering:** Do NOT alter `render_turnkey_prompt()`, `CONTAINER_GUIDANCE_TEMPLATE`, or inject synthetic prompts/outlines into turnkey prompts.
- **Arm Input Parity:** Baseline arms and superstate arms must receive identical prompt guidance.
- **Conventional Commits:** All git commits must use conventional commit messages with `--no-gpg-sign`.
- **Rust Tooling:** All Rust code must pass `cargo clippy --all-targets -- -D warnings` and `cargo test --all`.
- **Python Environment:** All Python checks must use `.venv/bin/python`.

---

### Task 1: `superstate-syntax` Engine Extensions

- **Depends on:** none

**Files:**
- Create: `crates/superstate-syntax/src/inspect.rs`
- Modify: `crates/superstate-syntax/src/lib.rs`
- Test: `crates/superstate-syntax/tests/test_inspect.rs`

**Interfaces:**
- Consumes: `SupportedLanguage`, `SymbolInfo`, `SyntaxError`, `extract_symbols` from `crates/superstate-syntax`
- Produces:
  ```rust
  pub fn detect_language(path: &Path) -> Option<SupportedLanguage>;
  pub fn extract_symbols_from_file(path: &Path) -> Result<(SupportedLanguage, String, Vec<SymbolInfo>), SyntaxError>;
  pub fn extract_symbol_source<'a>(source: &'a str, symbol: &SymbolInfo) -> &'a str;
  pub fn format_outline(symbols: &[SymbolInfo]) -> String;
  pub fn find_symbol<'a>(symbols: &'a [SymbolInfo], name: &str) -> Option<&'a SymbolInfo>;
  ```

- [ ] **Step 1: Write failing unit test in `crates/superstate-syntax/tests/test_inspect.rs`**
  Cover language detection for `.rs`, `.py`, `.pyx`, `.ts`, `.go`, unsupported files, symbol source slicing, and outline formatting.
- [ ] **Step 2: Run test to verify it fails**
  `cargo test -p superstate-syntax --test test_inspect` (Expected: compile error / FAIL).
- [ ] **Step 3: Implement `inspect.rs` and re-export in `lib.rs`**
  Implement `detect_language`, `extract_symbols_from_file`, `extract_symbol_source`, `format_outline`, and `find_symbol`.
- [ ] **Step 4: Run test to verify it passes**
  `cargo test -p superstate-syntax --test test_inspect` (Expected: PASS).
  `cargo clippy -p superstate-syntax --all-targets -- -D warnings` (Expected: clean).
- [ ] **Step 5: Commit changes**
  `git commit --no-gpg-sign -m "feat(syntax): add language detection, symbol slicing, and outline formatting"`

---

### Task 2: `superstate-cli` `inspect` Command Implementation & System Installation

- **Depends on:** Task 1

**Files:**
- Create: `crates/superstate-cli/src/commands/inspect.rs`
- Modify: `crates/superstate-cli/src/commands/mod.rs`
- Modify: `crates/superstate-cli/src/main.rs`
- Test: `crates/superstate-cli/tests/test_cli_inspect.rs`

**Interfaces:**
- Consumes: `superstate_syntax::inspect::*`
- Produces: CLI command `superstate inspect <path> [--symbol <name>] [--outline] [--lines <s:e>] [--json]`

- [ ] **Step 1: Write failing integration test in `crates/superstate-cli/tests/test_cli_inspect.rs`**
  Test default outline mode, `--symbol <name>`, `--lines <s:e>`, `--json`, and error exits for missing files or missing symbols.
- [ ] **Step 2: Run test to verify it fails**
  `cargo test -p superstate --test test_cli_inspect` (Expected: FAIL).
- [ ] **Step 3: Implement `inspect.rs` and wire in `main.rs`**
  Implement `InspectArgs` with clap, format output lines, handle missing symbols/files with clean error messages and exit code 1.
- [ ] **Step 4: Run test to verify it passes**
  `cargo test -p superstate --test test_cli_inspect` (Expected: PASS).
  `cargo test --all` and `cargo clippy --all-targets -- -D warnings` (Expected: 100% clean).
- [ ] **Step 5: Install release binary and verify CLI availability**
  Run: `cargo install --path crates/superstate-cli --locked --force`
  Verify: `~/.cargo/bin/superstate inspect --help` outputs available flags.
- [ ] **Step 6: Commit changes**
  `git commit --no-gpg-sign -m "feat(cli): add superstate inspect command for AST symbol extraction and slicing"`

---

### Task 3: Arm Input Parity Verification & Container Execution Check

- **Depends on:** Task 2

**Files:**
- Test: `tests/test_arm_input_parity.py` in `superstate-eval`

**Interfaces:**
- Consumes: Installed `superstate` binary and container bind-mount in `lab/sandbox/docker_manager.py`
- Produces: Verification evidence that arm parity is preserved and `superstate inspect` runs inside containers.

- [ ] **Step 1: Run arm input parity test suite**
  Run: `.venv/bin/python -m pytest tests/test_arm_input_parity.py -q`
  Confirm that guidance and prompts remain identical across arms.
- [ ] **Step 2: Verify in-container execution of `superstate inspect`**
  Run: `superstate inspect` against a sample Python file on host and inside container via `./run-in-container superstate inspect ...`.
- [ ] **Step 3: Run full `superstate-eval` test suite**
  Run: `.venv/bin/python -m pytest tests/ -q` (Confirm 343+ passed).
- [ ] **Step 4: Commit any test evidence or docs**
  `git commit --no-gpg-sign -m "test(eval): verify arm parity and in-container inspect availability"`
