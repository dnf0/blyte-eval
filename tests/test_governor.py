"""Tests for Machine-Aware Concurrency Governor."""

from __future__ import annotations

from lab.engine.governor import ConcurrencyGovernor, SystemSpecs


def test_calculate_concurrency_high_spec_machine() -> None:
    governor = ConcurrencyGovernor()
    specs = SystemSpecs(
        logical_cpus=12,
        total_ram_gb=24.0,
        available_ram_gb=18.0,
        free_disk_gb=120.0,
    )
    # 12 cpus // 2.5 = 4
    # 18 gb available // 4 = 4
    # (120 - 20) // 10 = 10
    concurrency = governor.calculate_max_concurrency(specs)
    assert concurrency == 4


def test_calculate_concurrency_ram_constrained_machine() -> None:
    governor = ConcurrencyGovernor()
    specs = SystemSpecs(
        logical_cpus=16,
        total_ram_gb=16.0,
        available_ram_gb=4.0,
        free_disk_gb=100.0,
    )
    # 16 // 2.5 = 6
    # 4 // 4 = 1
    # Available RAM is the bottleneck
    concurrency = governor.calculate_max_concurrency(specs)
    assert concurrency == 1


def test_calculate_concurrency_zero_when_disk_headroom_breached() -> None:
    governor = ConcurrencyGovernor()
    specs = SystemSpecs(
        logical_cpus=12,
        total_ram_gb=24.0,
        available_ram_gb=16.0,
        free_disk_gb=15.0,  # Below the 20 GB safety margin
    )
    # Usable disk is 0.0 -> must strictly return 0 workers to prevent host crash
    concurrency = governor.calculate_max_concurrency(specs)
    assert concurrency == 0


def test_calculate_concurrency_zero_when_insufficient_ram() -> None:
    governor = ConcurrencyGovernor()
    specs = SystemSpecs(
        logical_cpus=12,
        total_ram_gb=32.0,
        available_ram_gb=1.5,  # Less than 4.0 GB per worker
        free_disk_gb=100.0,
    )
    concurrency = governor.calculate_max_concurrency(specs)
    assert concurrency == 0


def test_calculate_concurrency_user_override() -> None:
    governor = ConcurrencyGovernor()
    specs = SystemSpecs(
        logical_cpus=12,
        total_ram_gb=24.0,
        available_ram_gb=16.0,
        free_disk_gb=100.0,
    )
    # Machine admits 4, but user overrides with 2
    concurrency = governor.calculate_max_concurrency(specs, user_max=2)
    assert concurrency == 2

    # Machine admits 4, user requests 10 -> clamped to machine max (4)
    concurrency_clamped = governor.calculate_max_concurrency(specs, user_max=10)
    assert concurrency_clamped == 4


def test_governor_slot_context_manager() -> None:
    governor = ConcurrencyGovernor()
    assert governor._active_slots == 0
    with governor.slot(timeout_sec=5.0, user_max=2) as acquired:
        assert acquired is True
        assert governor._active_slots == 1
    assert governor._active_slots == 0


def test_get_live_system_specs() -> None:
    governor = ConcurrencyGovernor()
    specs = governor.get_system_specs()
    assert specs.logical_cpus >= 1
    assert specs.total_ram_gb > 0
    assert specs.free_disk_gb > 0
