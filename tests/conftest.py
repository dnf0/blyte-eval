"""Tests never size themselves from the machine running them.

`AblationRunner.run_task` takes a slot from a real `ConcurrencyGovernor`, which sizes itself from
the live host. On a small CI runner that came to zero slots and each such test waited out the
300-second slot timeout; on a large laptop it passed. Every test sees the same fixed machine unless
it is marked `live_specs` (the one test that checks live detection itself).
"""

import pytest

from lab.engine.governor import ConcurrencyGovernor, SystemSpecs

FIXED_MACHINE = SystemSpecs(
    logical_cpus=16, total_ram_gb=64.0, available_ram_gb=48.0, free_disk_gb=500.0
)


@pytest.fixture(autouse=True)
def fixed_machine(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    if request.node.get_closest_marker("live_specs"):
        return
    monkeypatch.setattr(ConcurrencyGovernor, "get_system_specs", lambda self: FIXED_MACHINE)
