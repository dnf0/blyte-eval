"""Tests for Machine-Aware Concurrency Governor."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

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
    # 24 gb // 4 = 6
    # (120 - 20) // 10 = 10
    concurrency = governor.calculate_max_concurrency(specs)
    assert concurrency == 4


def test_calculate_concurrency_ram_constrained_machine() -> None:
    governor = ConcurrencyGovernor()
    specs = SystemSpecs(
        logical_cpus=16,
        total_ram_gb=8.0,
        available_ram_gb=4.0,
        free_disk_gb=100.0,
    )
    # 16 // 2.5 = 6
    # 8 // 4 = 2
    # RAM is the bottleneck
    concurrency = governor.calculate_max_concurrency(specs)
    assert concurrency == 2


def test_calculate_concurrency_disk_constrained_machine() -> None:
    governor = ConcurrencyGovernor()
    specs = SystemSpecs(
        logical_cpus=12,
        total_ram_gb=24.0,
        available_ram_gb=16.0,
        free_disk_gb=25.0,  # Only 5 GB above the 20 GB safety margin
    )
    # (25 - 20) // 10 = 0 -> clamped to 1
    concurrency = governor.calculate_max_concurrency(specs)
    assert concurrency == 1


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


def test_get_live_system_specs() -> None:
    governor = ConcurrencyGovernor()
    specs = governor.get_system_specs()
    assert specs.logical_cpus >= 1
    assert specs.total_ram_gb > 0
    assert specs.free_disk_gb > 0
