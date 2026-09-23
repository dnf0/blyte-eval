#!/bin/bash
# Verify the perimeter guards actually fire, in ~2 minutes instead of a ~60-minute canary.
#
# WHY THIS EXISTS
# ---------------
# Four benchmark runs on 2026-09-21 were spent discovering wiring bugs rather than measuring
# anything: a binary swapped mid-run, a NameError at the confirmation gate, a guard whose denial
# text ended the worker's turn, and hooks that invoked yesterday's binary because the command was
# a bare name resolved through PATH. None of those needed a task corpus, a sealed grader or a
# scoring pass. They needed one agy turn against a prepared workspace.
#
# Verify mechanism cheaply and deterministically; spend benchmark runs on outcomes.
#
# Usage:  scripts/guard_smoke.sh [path-to-superstate-binary]
set -uo pipefail

BIN="${1:-/Users/danielfisher/repos/superstate/target/release/superstate}"
[ -x "$BIN" ] || { echo "no executable superstate at $BIN" >&2; exit 1; }

# The budget under test. Read from the binary's own --help rather than duplicated here, so
# this smoke test tracks the shipped default instead of failing whenever it is varied.
THRESHOLD="${2:-$("$BIN" guard pre-tool-use --help 2>/dev/null \
  | sed -n 's/.*\[default: \([0-9][0-9]*\)\].*/\1/p' | head -1)}"
[ -n "$THRESHOLD" ] || { echo "could not determine the default read budget from $BIN" >&2; exit 1; }

WS=$(mktemp -d "/tmp/guard_smoke.XXXXXX")
trap 'rm -rf "$WS"' EXIT
mkdir -p "$WS/.agents" "$WS/internal"

# A file comfortably over the budget, with real symbols so the AST outline is meaningful.
# Sized FROM the threshold: a fixture with a hardcoded length silently stops exercising the
# deny path the moment the budget is raised past it.
FUNCS=$(( THRESHOLD / 2 ))   # 4 lines each, so ~2x the budget
{
  echo "package internal"
  for i in $(seq 1 "$FUNCS"); do
    printf 'func Handler%d(x int) int {\n\treturn x + %d\n}\n\n' "$i" "$i"
  done
} > "$WS/internal/handlers.go"
LINES=$(wc -l < "$WS/internal/handlers.go" | tr -d ' ')

# Hooks exactly as DaemonRunner provisions them, including the absolute binary path.
cat > "$WS/.agents/hooks.json" <<EOF
{
  "superstate-file-guard": {
    "PreToolUse": [
      { "matcher": "view_file|View|read_file",
        "hooks": [ { "command": "$BIN guard pre-tool-use --threshold-lines $THRESHOLD" } ] }
    ]
  },
  "superstate-command-guard": {
    "PreToolUse": [
      { "matcher": "run_command|manage_task",
        "hooks": [ { "command": "$BIN guard pre-command --debounce-sec 30" } ] }
    ]
  }
}
EOF

echo "workspace: $WS"
echo "binary:    $BIN"
echo "fixture:   internal/handlers.go ($LINES lines, budget $THRESHOLD)"
echo

fail=0
check() { # name, expected(allow|deny), payload, [cwd]
  local name="$1" want="$2" payload="$3" cwd="${4:-$WS/.agents}"
  local got
  got=$(cd "$cwd" && echo "$payload" | SUPERSTATE_WORKTREE_PATH="$WS" "$BIN" guard "$5" ${6:-} 2>/dev/null \
        | sed -n 's/.*"decision":"\([a-z]*\)".*/\1/p')
  if [ "$got" = "$want" ]; then
    printf '  ok      %-52s -> %s\n' "$name" "$got"
  else
    printf '  FAIL    %-52s -> %s (wanted %s)\n' "$name" "${got:-<no decision>}" "$want"
    fail=1
  fi
}

echo "file viewing tool:"
check "whole-file read, relative path from .agents cwd" deny \
  '{"tool_name":"view_file","tool_input":{"path":"internal/handlers.go"}}' "$WS/.agents" pre-tool-use
check "bounded read (lines 10-60)" allow \
  '{"tool_name":"view_file","tool_input":{"path":"internal/handlers.go","start_line":10,"end_line":60}}' "$WS/.agents" pre-tool-use

# The read cache. A distinct helper because these checks turn on WHY a read was refused --
# "you already hold this" and "this exceeds the budget" are both `deny` to the caller, and a
# test that cannot tell them apart would pass with the cache switched off.
cache_check() { # name, expected(allow|cached), start, end
  local name="$1" want="$2" body got
  body=$(cd "$WS/.agents" && printf '{"toolCall":{"name":"view_file","args":{"AbsolutePath":"%s","StartLine":%s,"EndLine":%s}}}' \
          "$WS/internal/handlers.go" "$3" "$4" \
          | SUPERSTATE_WORKTREE_PATH="$WS" "$BIN" guard pre-tool-use --read-cache true 2>/dev/null)
  case "$body" in
    *"Already in context"*) got=cached ;;
    *'"decision":"allow"'*) got=allow ;;
    *) got=deny ;;
  esac
  if [ "$got" = "$want" ]; then
    printf '  ok      %-52s -> %s\n' "$name" "$got"
  else
    printf '  FAIL    %-52s -> %s (wanted %s)\n' "$name" "${got:-<none>}" "$want"
    fail=1
  fi
}

# Enabled explicitly: the cache defaults OFF after EXP-081 measured it a regression. These
# checks cover the MECHANISM, which is still switchable and still has to work when switched on.
echo "read cache (explicitly enabled; default is off -- FINDINGS 13.25):"
# A window the earlier "bounded read" check did NOT touch -- it read 10-60, and reusing it
# here silently started this sequence one step in, reporting a first read as a cache hit.
cache_check "first read of a window"                        allow  100 160
cache_check "identical window is served from context"       cached 100 160
cache_check "insisting on it is honoured"                   allow  100 160
cache_check "a window inside one already held"              cached 110 140
cache_check "a window never fetched"                        allow  300 340
printf '\n# line added by the smoke test\n' >> "$WS/internal/handlers.go"
cache_check "editing the file invalidates what was held"    allow  10 60
echo

echo "shell channel:"
check "cat whole file" deny \
  '{"tool_name":"run_command","tool_input":{"CommandLine":"cat internal/handlers.go"}}' "$WS/.agents" pre-command
check "cat piped to grep" deny \
  '{"tool_name":"run_command","tool_input":{"CommandLine":"cat internal/handlers.go | grep Handler7"}}' "$WS/.agents" pre-command
check "head -50 (bounded)" allow \
  '{"tool_name":"run_command","tool_input":{"CommandLine":"head -50 internal/handlers.go"}}' "$WS/.agents" pre-command
check "go test (not a read)" allow \
  '{"tool_name":"run_command","tool_input":{"CommandLine":"go test ./..."}}' "$WS/.agents" pre-command

echo "polling:"
POLL='{"tool_name":"run_command","tool_input":{"CommandLine":"ps aux | grep build"}}'
# A 2s window proves the same property as the production 30s, without the wait.
check "first process inspection" allow "$POLL" "$WS/.agents" pre-command "--debounce-sec 2"
START=$(date +%s)
check "repeat within cooldown is throttled, never denied" allow "$POLL" "$WS/.agents" pre-command "--debounce-sec 2"
WAITED=$(( $(date +%s) - START ))
if [ "$WAITED" -ge 1 ]; then
  printf '  ok      %-52s -> delayed %ss\n' "repeat was delayed rather than refused" "$WAITED"
else
  printf '  FAIL    %-52s -> returned instantly; not throttled\n' "repeat was delayed rather than refused"
  fail=1
fi

echo
DEN="$WS/.agent-state/guard-denials.jsonl"
if [ -s "$DEN" ]; then
  echo "  ok      denials recorded: $(wc -l < "$DEN" | tr -d ' '), $(awk -F'"lines":' '{gsub(/[^0-9].*/,"",$2); s+=$2} END {print s+0}' "$DEN") lines withheld"
else
  echo "  FAIL    guard-denials.jsonl is empty: the mechanism leaves no trace"
  fail=1
fi

echo
[ "$fail" -eq 0 ] && echo "PERIMETER OK" || echo "PERIMETER BROKEN"
exit $fail
