"""Machine-aware dynamic concurrency governor for isolated evaluation execution."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import logging
import os
from pathlib import Path
import shutil
import threading
import time
from typing import Generator

logger = logging.getLogger("superstate_eval.governor")


@dataclass(frozen=True)
class SystemSpecs:
    """Hardware capacity snapshot used to determine safe concurrency bounds."""

    logical_cpus: int
    total_ram_gb: float
    available_ram_gb: float
    free_disk_gb: float


class ConcurrencyGovernor:
    """Governs evaluation concurrency dynamically based on host machine resources."""

    def __init__(
        self,
        cpus_per_worker: float = 2.5,
        ram_gb_per_worker: float = 4.0,
        disk_headroom_gb: float = 20.0,
        disk_gb_per_worker: float = 10.0,
        disk_check_path: Path | str = "/",
    ) -> None:
        self.cpus_per_worker = cpus_per_worker
        self.ram_gb_per_worker = ram_gb_per_worker
        self.disk_headroom_gb = disk_headroom_gb
        self.disk_gb_per_worker = disk_gb_per_worker
        self.disk_check_path = Path(disk_check_path)
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._active_slots: int = 0

    def get_system_specs(self) -> SystemSpecs:
        """Query live hardware specs from the OS."""
        logical_cpus = os.cpu_count() or 2

        # Memory detection
        try:
            import psutil

            mem = psutil.virtual_memory()
            total_ram_gb = round(mem.total / (1024**3), 2)
            available_ram_gb = round(mem.available / (1024**3), 2)
        except ImportError:
            # Fallback if psutil is not installed
            total_ram_gb = 16.0
            available_ram_gb = 8.0

        # Disk space detection
        disk = shutil.disk_usage(self.disk_check_path)
        free_disk_gb = round(disk.free / (1024**3), 2)

        return SystemSpecs(
            logical_cpus=logical_cpus,
            total_ram_gb=total_ram_gb,
            available_ram_gb=available_ram_gb,
            free_disk_gb=free_disk_gb,
        )

    def calculate_max_concurrency(
        self, specs: SystemSpecs | None = None, user_max: int | None = None
    ) -> int:
        """Calculate maximum safe concurrency given hardware capacity and optional user ceiling.

        Returns 0 if available resources (RAM or Disk) are below minimum safety margins.
        """
        if specs is None:
            specs = self.get_system_specs()

        # 1. CPU-based allowance (must have at least 1 core for any run)
        cpu_workers = int(specs.logical_cpus // self.cpus_per_worker)
        if cpu_workers < 1:
            cpu_workers = 1 if specs.logical_cpus >= 1 else 0

        # 2. Available RAM-based allowance (never use total_ram_gb)
        ram_workers = int(specs.available_ram_gb // self.ram_gb_per_worker)

        # 3. Disk-based allowance (strictly enforce disk_headroom_gb margin)
        usable_disk = max(0.0, specs.free_disk_gb - self.disk_headroom_gb)
        disk_workers = int(usable_disk // self.disk_gb_per_worker)

        # Hardware bottleneck allows 0 if any resource guard rail is breached
        hardware_max = min(cpu_workers, ram_workers, disk_workers)

        if user_max is not None and user_max > 0:
            final_concurrency = min(hardware_max, user_max)
        else:
            final_concurrency = hardware_max

        logger.info(
            "Calculated concurrency: %d (CPU limit=%d, RAM limit=%d, Disk limit=%d, User override=%s)",
            final_concurrency,
            cpu_workers,
            ram_workers,
            disk_workers,
            user_max,
        )
        return max(0, final_concurrency)

    def acquire_slot(self, timeout_sec: float = 300.0, user_max: int | None = None) -> bool:
        """Block until an execution slot is available under live resource constraints."""
        start_time = time.time()
        with self._condition:
            while True:
                max_allowed = self.calculate_max_concurrency(user_max=user_max)
                if max_allowed > 0 and self._active_slots < max_allowed:
                    self._active_slots += 1
                    logger.debug(
                        "Acquired worker slot (active: %d / %d)", self._active_slots, max_allowed
                    )
                    return True

                elapsed = time.time() - start_time
                if elapsed >= timeout_sec:
                    logger.warning("Timed out after %.1fs waiting for worker slot", timeout_sec)
                    return False

                self._condition.wait(timeout=min(5.0, timeout_sec - elapsed))

    def release_slot(self) -> None:
        """Release an active execution slot and notify waiting tasks."""
        with self._condition:
            if self._active_slots > 0:
                self._active_slots -= 1
            self._condition.notify_all()
            logger.debug("Released worker slot (active remaining: %d)", self._active_slots)

    @contextmanager
    def slot(
        self, timeout_sec: float = 300.0, user_max: int | None = None
    ) -> Generator[bool, None, None]:
        """Context manager acquiring a dynamic concurrency slot."""
        acquired = self.acquire_slot(timeout_sec=timeout_sec, user_max=user_max)
        try:
            yield acquired
        finally:
            if acquired:
                self.release_slot()
