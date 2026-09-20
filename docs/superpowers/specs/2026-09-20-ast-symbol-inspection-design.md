# Design Specification: Native AST Symbol Inspection & Deterministic Context Bounding

**Author:** Antigravity / DeepMind Pair Programming  
**Date:** 2026-09-20  
**Status:** Approved  
**Topic:** AST Symbol Inspection & Deterministic Context Slicing (`superstate-syntax`, `superstate-cli`, `superstate-mcp`)

---

## 1. Executive Summary & Problem Context

Empirical evaluation of `superstate_daemon_full` on `terminal-bench/build-cython-ext` demonstrated the efficacy of tool output shunting:
- Output shunting eliminated long compiler streams and 400-line unified diffs, reducing input tokens by **79,432 tokens (-10.8%)** and execution cost from **$0.804 to $0.704 (-12.5%)** with 100% test pass rate (11/11 tests).
- However, detailed transcript analysis of the 136 agent steps revealed that **85,163 characters (~21,290 tokens)** of raw source code were repeatedly ingested via 37 native `view_file` calls.
- Because `view_file` reads entire 400-to-800 line files, conversational LLM context accumulated quadratically from 1,029 tokens at step 1 up to 53,612 tokens at step 135.
- While `repos/superstate` already vendors Tree-sitter parsers for Python, Rust, TypeScript, and Go in `crates/superstate-syntax`, that engine was never exposed as a CLI command or an MCP tool.

This specification exposes `superstate-syntax` as a first-class, deterministic code inspection tool (`superstate inspect`) to enable bounded symbol slicing and compact outlines without whole-file dumping.

---

## 2. Strict Invariants & Non-Goals

### 2.1 The Zero Prompt Engineering Invariant
<HARD-GATE>
**Zero Harness-Level Prompt Engineering.**
In accordance with `AGENTS.md` and past benchmark retrospectives:
1. No synthetic AST outlines shall be injected into `render_turnkey_prompt()` or prompt templates.
2. No behavioral steering, special rules, or prompt additions shall be injected into `CONTAINER_GUIDANCE_TEMPLATE`.
3. Strict arm input parity shall be preserved across all arms (`vanilla`, `superstate_mcp`, `superstate_daemon_full`).
4. `superstate inspect` is implemented strictly as a deterministic developer tool, discoverable via `--help` and environment availability.
</HARD-GATE>

### 2.2 Non-Goals
- Do not introduce AST-based auto-editing or code transformations.
- Do not modify how verification commands or sealed graders are executed.
- Do not alter turn loop structures or lease extension mechanics.

---

## 3. Architecture & Interfaces

```
+-----------------------------------------------------------------------------------+
| Host or Sandbox Container                                                         |
|                                                                                   |
|   +---------------------------------------------------------------------------+   |
|   | Agent / Driver Turn Loop (run_command / CLI / MCP)                       |   |
|   +-------------------------------------+-------------------------------------+   |
|                                         |                                         |
|                                         v                                         |
|   +---------------------------------------------------------------------------+   |
|   | superstate inspect <file> [OPTIONS]                                       |   |
|   |                                                                           |   |
|   |   --symbol <name>   -> Extracts exact function/class body [lines S-E]     |   |
|   |   --outline         -> Emits 1-line-per-symbol signature outline (default)|   |
|   |   --lines <S:E>     -> Bounded line-slice with line numbers               |   |
|   |   --json            -> Structured JSON output for programmatic ingestion  |   |
|   +-------------------------------------+-------------------------------------+   |
|                                         |                                         |
|                                         v                                         |
|   +---------------------------------------------------------------------------+   |
|   | superstate-syntax (Tree-sitter AST Polyglot Engine)                      |   |
|   | - SupportedLanguage: Rust, Python, TypeScript, Go                         |   |
|   | - extract_symbols(), detect_language(), extract_symbol_source()           |   |
|   +---------------------------------------------------------------------------+   |
+-----------------------------------------------------------------------------------+
```

### 3.1 `superstate-syntax` Engine Enhancements

Location: `crates/superstate-syntax/src/`

#### Language Detection
```rust
pub fn detect_language(path: &Path) -> Option<SupportedLanguage> {
    match path.extension().and_then(|ext| ext.to_str()) {
        Some("rs") => Some(SupportedLanguage::Rust),
        Some("py") | Some("pyx") => Some(SupportedLanguage::Python),
        Some("ts") | Some("tsx") | Some("js") | Some("jsx") => Some(SupportedLanguage::TypeScript),
        Some("go") => Some(SupportedLanguage::Go),
        _ => None,
    }
}
```

#### Symbol Source Extraction & Outlining
```rust
/// Extracts the slice of source code corresponding to a symbol's line range.
pub fn extract_symbol_source<'a>(source: &'a str, symbol: &SymbolInfo) -> &'a str;

/// Formats a compact AST outline with 1 line per symbol.
pub fn format_outline(symbols: &[SymbolInfo]) -> String;

/// Resolves a symbol by exact or case-insensitive name.
pub fn find_symbol<'a>(symbols: &'a [SymbolInfo], name: &str) -> Option<&'a SymbolInfo>;
```

### 3.2 `superstate-cli` Command: `superstate inspect`

Location: `crates/superstate-cli/src/commands/inspect.rs` and `main.rs`

#### CLI Definition
```rust
#[derive(clap::Args, Debug)]
pub struct InspectArgs {
    /// Path to target source file to inspect
    pub path: PathBuf,

    /// Extract and print only the body of a specific function, class, or struct
    #[arg(long)]
    pub symbol: Option<String>,

    /// Print compact symbol outline (signatures and line numbers)
    #[arg(long)]
    pub outline: bool,

    /// Print bounded line range in format 'start:end' (1-indexed)
    #[arg(long)]
    pub lines: Option<String>,

    /// Emit output in structured JSON format
    #[arg(long)]
    pub json: bool,
}
```

#### Output Formats

1. **Default Outline Mode (`superstate inspect <file>` or `--outline`)**:
```text
=== Outline: pyknotid/invariants.py (Python) ===
- [Function] _alexander_numpy(crossings, variable=-1.0, quadrant='lr') [lines 134-180]
- [Function] alexander_polynomial(crossings, variable=-1.0) [lines 182-225]
- [Class] KnotInvariant [lines 230-310]
```

2. **Targeted Symbol Extraction (`superstate inspect <file> --symbol _alexander_numpy`)**:
```text
=== Symbol: _alexander_numpy [lines 134-180] in pyknotid/invariants.py ===
134: def _alexander_numpy(crossings, variable=-1.0, quadrant='lr'):
135:     '''
...
180:     return poly_val
```

3. **Line Range Slicing (`superstate inspect <file> --lines 134:145`)**:
```text
=== Lines 134-145 in pyknotid/invariants.py ===
134: def _alexander_numpy(crossings, variable=-1.0, quadrant='lr'):
135:     '''
...
145:     matrix = n.zeros((num_crossings, num_crossings), dtype=dtype)
```

4. **JSON Mode (`--json`)**:
Emits `Vec<SymbolInfo>` serialised as JSON.

---

## 4. Error Handling & Edge Cases

| Condition | Behavior | Exit Code |
|---|---|---|
| File does not exist | `Error: file not found at <path>` | 1 |
| Unsupported file extension | Falls back to line range or prints `Error: unsupported language for AST parsing in '<path>'. Use --lines <start:end>` | 1 |
| Symbol not found in file | Prints `Error: symbol '<name>' not found in <path>. Available symbols: [s1, s2, ...]` | 1 |
| Invalid `--lines` syntax | Prints `Error: invalid line range '<arg>'. Expected format 'start:end' (e.g. 10:50)` | 1 |
| Line range out of bounds | Clamps gracefully to `[1, total_lines]` | 0 |
| Empty file | Prints empty outline or empty output gracefully | 0 |

---

## 5. Testing & Verification Strategy

### 5.1 Unit Tests (`crates/superstate-syntax`)
- `test_detect_language`: Tests `.py`, `.rs`, `.ts`, `.go`, and unsupported extensions (`.c`, `.json`).
- `test_extract_symbol_source`: Verifies exact line boundary slicing without off-by-one errors.
- `test_format_outline`: Verifies compact string formatting.
- `test_find_symbol`: Verifies exact and case-insensitive matching.

### 5.2 Integration Tests (`crates/superstate-cli`)
- `test_cli_inspect_outline`: Verifies default outline output across Python and Rust files.
- `test_cli_inspect_symbol`: Verifies extracted body matches function definition.
- `test_cli_inspect_lines`: Verifies line numbers and slice content.
- `test_cli_inspect_json`: Verifies valid JSON array output.
- `test_cli_inspect_missing_file_and_symbol`: Verifies non-zero exit codes and helpful error messages.

### 5.3 Parity & Regression Gates (`superstate-eval`)
- `tests/test_arm_input_parity.py`: Verifies zero prompt engineering; guidance template remains identical.
- Re-run full 343-test suite in `superstate-eval`.
- Empirical verification on `terminal-bench/build-cython-ext`.
