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
    # (24 total - 8 reserve) // 4 = 4
    # (120 - 20) // 10 = 10
    concurrency = governor.calculate_max_concurrency(specs)
    assert concurrency == 4


def test_calculate_concurrency_ram_constrained_machine() -> None:
    governor = ConcurrencyGovernor()
    specs = SystemSpecs(
        logical_cpus=16,
        total_ram_gb=12.0,
        available_ram_gb=9.0,
        free_disk_gb=100.0,
    )
    # 16 // 2.5 = 6
    # (12 total - 8 reserve) // 4 = 1
    # Installed RAM is the bottleneck
    concurrency = governor.calculate_max_concurrency(specs)
    assert concurrency == 1


def test_concurrency_ignores_transient_os_reported_availability() -> None:
    """A busy desktop must not shrink the cohort.

    macOS reports available as free+inactive, excluding cached/compressed pages
    the kernel reclaims on demand, so a 24 GB host under load can report under
    5 GB available while being perfectly able to run the cohort.
    """
    governor = ConcurrencyGovernor()
    idle = SystemSpecs(
        logical_cpus=12, total_ram_gb=24.0, available_ram_gb=20.0, free_disk_gb=120.0
    )
    busy = SystemSpecs(
        logical_cpus=12, total_ram_gb=24.0, available_ram_gb=4.7, free_disk_gb=120.0
    )
    assert governor.calculate_max_concurrency(idle) == governor.calculate_max_concurrency(busy)


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
        total_ram_gb=10.0,  # Only 2 GB usable after the 8 GB host reserve
        available_ram_gb=9.0,
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


def test_concurrency_is_sized_on_the_real_container_footprint() -> None:
    """Tasks declare their own memory_mb; sizing on the default overcommits."""
    governor = ConcurrencyGovernor()
    specs = SystemSpecs(
        logical_cpus=12, total_ram_gb=24.0, available_ram_gb=20.0, free_disk_gb=200.0
    )

    # Default 4 GB/worker: (24 - 8) // 4 = 4, capped by CPU at 4.
    assert governor.calculate_max_concurrency(specs) == 4

    # Real tasks declare 8 GB. 4 x 8 = 32 GB on a 24 GB host would thrash.
    assert governor.calculate_max_concurrency(specs, ram_gb_per_worker=8.0) == 2
