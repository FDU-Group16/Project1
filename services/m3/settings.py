"""Explicit dependency selection; production never falls back to demo data."""
from dataclasses import dataclass
import os
import math


@dataclass(frozen=True)
class Settings:
    mode: str = "production"
    directory_mode: str = "unavailable"
    m1_mode: str = "http"
    database_url: str = ""
    identity_base_url: str = ""
    d_base_url: str = ""
    directory_timeout_seconds: float = 3
    m1_base_url: str = ""
    m1_token: str = ""
    worker_enabled: bool = True
    worker_interval_seconds: float = 1
    assignment_sla_hours: float = 24
    repair_sla_hours: float = 48
    m1_timeout_seconds: float = 3

    def __post_init__(self):
        if self.mode not in {"development", "test", "production"}:
            raise ValueError("Invalid M3_MODE")
        if self.directory_mode not in {"unavailable", "development", "http"}:
            raise ValueError("Invalid M3_DIRECTORY_MODE")
        if self.m1_mode not in {"http", "development-http"}:
            raise ValueError("Invalid M3_M1_MODE")
        if self.mode == "production" and (
            self.directory_mode == "development" or self.m1_mode != "http"
        ):
            raise ValueError("Development dependencies are forbidden in production")
        if self.mode == "production" and self.database_url.startswith("sqlite"):
            raise ValueError("SQLite is development/test only")
        if not all(math.isfinite(value) and value > 0 for value in (
            self.worker_interval_seconds, self.assignment_sla_hours,
            self.repair_sla_hours, self.m1_timeout_seconds, self.directory_timeout_seconds
        )):
            raise ValueError("M3 time settings must be positive")

    @classmethod
    def from_env(cls):
        return cls(
            mode=os.getenv("M3_MODE", "production"),
            directory_mode=os.getenv("M3_DIRECTORY_MODE", "unavailable"),
            m1_mode=os.getenv("M3_M1_MODE", "http"),
            database_url=os.getenv("M3_DATABASE_URL", ""),
            identity_base_url=os.getenv("M3_IDENTITY_BASE_URL", ""),
            d_base_url=os.getenv("D_BASE_URL", ""),
            directory_timeout_seconds=float(os.getenv("M3_DIRECTORY_TIMEOUT_SECONDS", "3")),
            m1_base_url=os.getenv("M3_M1_BASE_URL", ""),
            m1_token=os.getenv("M3_M1_TOKEN", ""),
            worker_enabled=os.getenv("M3_WORKER_ENABLED", "true").lower() == "true",
            worker_interval_seconds=float(os.getenv("M3_WORKER_INTERVAL_SECONDS", "1")),
            assignment_sla_hours=float(os.getenv("M3_ASSIGNMENT_SLA_HOURS", "24")),
            repair_sla_hours=float(os.getenv("M3_REPAIR_SLA_HOURS", "48")),
            m1_timeout_seconds=float(os.getenv("M3_M1_TIMEOUT_SECONDS", "3")),
        )
