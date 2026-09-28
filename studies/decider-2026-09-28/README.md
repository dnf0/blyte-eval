# decider trial (2026-09-28): a local Jev-like model as a cheap judge

**Testing only.** Nothing here is wired into blyte. Model: [Mapika/decider](https://github.com/Mapika/decider)
(Apache-2.0), run locally on an Apple-silicon Mac from an isolated environment
(`~/.local/share/decider-venv`, weights in `~/.cache/decider/`). The write-up is the "Decider Trial"
report (a private artifact); this folder holds everything needed to rerun it.

## Tests

| script | question | data |
|---|---|---|
| `make_faults.py` → `score_gate.py` | Why did this check fail: code, environment or flaky? | 23 failures produced for real by breaking throwaway copies of blyte and blyte-eval (`data/gate_cases.jsonl`) |
| `score_gate.py` on `data/gate_cases_real.jsonl` | same | 23 real grader outputs of failed model changes (code) and 4 real eval infrastructure errors |
| `score_cmd.py`, `score_cmd_v2.py` | Does this command change shared state outside the project? (one question; then two: modifies? and outside?) | 120 commands sampled from blyte's event logs and labelled by hand, plus 22 written hard cases (`data/cmd_items.json`; labels in the script) |
| `score_progress.py` | Is the run making progress or going in circles? | windows of 15 tool calls from 9 failed and 60 verified recorded runs |
| `bench.py` | the gate and command tests per model variant: accuracy, latency, peak memory | v2 (bf16 on MPS), v2.1 Q4_K_M and 2B v11 Q4_K_M (llama.cpp Metal) |
| `calibration.py` | when it says p, is it right p of the time? | every answer from `bench.py` |
| `score_tasks.py` | Is this plan task specified well enough? | 55 plan tasks with their blyte verdicts |

The rule baselines are in the scripts. The gate rule was fixed before the cases were generated; the
command rule was written after seeing the sample, which flatters it.

## Headline results

- **Gate triage works.** Fix-or-stop (code against environment or flaky) was right on 96–100% of cases
  for every variant, against 87–89% for the rule, with no real code failure called environmental.
  Sending only the last 1,500 characters kept the accuracy and cut latency from about 15 s to about 1 s.
- **The command check needs precise questions.** One broad question: 89% with 13 false alarms (the rule
  94%). Two precise questions: 94%, 5 false alarms, and none on the hard cases.
- **Stuck-run detection is weak** (AUC 0.63–0.72, 9 failed runs). **Task-specification judgement shows no
  signal** (AUC about 0.5).
- **Calibration is good** (ECE 0.04–0.06): answers at 90% confidence or more were right 97–100% of the time.
- **Variants on this Mac:** v2 bf16 10.3 GB peak, 0.48 s median; v2.1 Q4 4.8 GB, 0.36 s, the same gate
  and command accuracy; 2B Q4 2.5 GB, 0.16 s, the best at gate triage and useless for the command check.

Limits: small sets, cases built and labelled by one person, one machine.
