"""The default measurement must contain no arm-specific prompt engineering."""

from __future__ import annotations

import os
from unittest.mock import patch

from lab.engine.prompt_contracts import ENV_FLAG, apply_contract, contracts_enabled


def test_contracts_are_off_by_default() -> None:
    """The thesis is that managing state produces the gain, so nothing else may differ.

    Three behavioural contracts were injected into superstate arms only, while vanilla and
    superpowers received none. That made published lift a mix of control plane and
    hand-tuned prompt.
    """
    with patch.dict(os.environ, {}, clear=True):
        assert contracts_enabled() is False
        assert apply_contract("PROMPT", "CONTRACT", "superstate") == "PROMPT"


def test_contracts_can_be_re_enabled_explicitly() -> None:
    """Preserved, not deleted -- reproducing historical runs must remain possible."""
    with patch.dict(os.environ, {ENV_FLAG: "1"}, clear=True):
        assert contracts_enabled() is True
        assert apply_contract("PROMPT", "CONTRACT", "superstate") == "PROMPT\n\nCONTRACT"


def test_no_adapter_injects_a_contract_directly() -> None:
    """Every injection must route through the switch, or the default silently leaks."""
    import pathlib

    offenders = []
    for path in pathlib.Path("lab/engine/adapters").glob("*.py"):
        for num, line in enumerate(path.read_text().splitlines(), 1):
            stripped = line.strip()
            if "EXECUTION_CONTRACT" not in stripped:
                continue
            # Definitions, imports and comments are fine; f-string interpolation is not.
            if stripped.startswith(("#", "TARGETED_", "AUTONOMOUS_", "from ", "import ")):
                continue
            if "{AUTONOMOUS_MCP_EXECUTION_CONTRACT}" in stripped or "{contract}" in stripped:
                offenders.append(f"{path.name}:{num}")
    assert not offenders, f"contracts injected without the switch: {offenders}"
