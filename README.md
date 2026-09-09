# superstate-eval

Independent local evaluation lab and differential testing testbed for [`superstate`](https://github.com/climate-x-org/superstate) (Rust) and `agent-rules` (Python) state machine architectures.

## Purpose

1. **Deterministic Parity Testing**: Prove byte-level, DAG, and verification gate parity between `superstate state` (Rust) and `agent-rules state` (Python) with zero LLM API cost.
2. **Efficacy & Ablation Evaluation**: Test whether progress-earned milestone state engines provide a measurable win rate and cost-efficiency advantage over unguided (Vanilla) and skill-guided (Superpowers) execution.
3. **Docker Lifecycle & Disk Management**: Prevent host disk saturation via guaranteed post-task container teardown and pre-flight disk space watchdogs.

## Quick Start

```bash
# Setup virtual environment and dependencies
uv sync

# Run zero-cost differential parity test suite
make parity

# Run all test suites
make test

# Manually trigger Docker system and volume cleanup
make clean-docker
```
