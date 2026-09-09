"""Machine-aware dynamic concurrency governor for isolated evaluation execution."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import shutil
import threading
from typing import Optional

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
        """Calculate maximum safe concurrency given hardware capacity and optional user ceiling."""
        if specs is None:
            specs = self.get_system_specs()

        # 1. CPU-based allowance
        cpu_workers = max(1, int(specs.logical_cpus // self.cpus_per_worker))

        # 2. RAM-based allowance
        ram_workers = max(1, int(specs.total_ram_gb // self.ram_gb_per_worker))

        # 3. Disk-based allowance
        usable_disk = max(0.0, specs.free_disk_gb - self.disk_headroom_gb)
        disk_workers = max(1, int(usable_disk // self.disk_gb_per_worker))

        # Hardware bottleneck
        hardware_max = min(cpu_workers, ram_workers, disk_workers)

        if user_max is not None and user_max > 0:
            final_concurrency = min(hardware_max, user_max)
        else:
            final_concurrency = hardware_max

        logger.info(
            f"Calculated concurrency: {final_concurrency} "
            f"(CPU limit={cpu_workers}, RAM limit={ram_workers}, Disk limit={disk_workers}, "
            f"User override={user_max})"
        )
        return final_concurrency
