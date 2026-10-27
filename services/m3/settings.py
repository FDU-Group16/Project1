"""Explicit startup configuration; never silently enable temporary providers."""

import math
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    mode: str = 'unconfigured'
    database_url: str | None = None
    m1_mode: str = 'unavailable'
    m1_url: str = ''
    m1_token: str = ''
    assignment_hours: float = 24.0
    repair_hours: float = 48.0
    worker_interval: float = 2.0

    def __post_init__(self):
        if self.mode not in ('unconfigured', 'development', 'production'):
            raise ValueError('M3_MODE must be unconfigured, development, or production')
        if self.m1_mode not in ('unavailable', 'stub', 'http'):
            raise ValueError('M3_M1_MODE must be unavailable, stub, or http')
        if self.mode != 'development' and self.m1_mode == 'stub':
            raise ValueError('M1 stub is only allowed in explicit development mode')
        for value in (self.assignment_hours, self.repair_hours):
            if not math.isfinite(value) or not 0 < value <= 8760:
                raise ValueError('SLA hours must be finite and in (0, 8760]')
        if not math.isfinite(self.worker_interval) or not 0.05 <= self.worker_interval <= 60:
            raise ValueError('Worker interval must be in [0.05, 60] seconds')
        if self.mode != 'development' and self.database_url and self.database_url.startswith('sqlite:'):
            raise ValueError('SQLite is only allowed in explicit development mode')

    @classmethod
    def from_env(cls):
        return cls(mode=os.getenv('M3_MODE', 'unconfigured'),
                   database_url=os.getenv('M3_DATABASE_URL'),
                   m1_mode=os.getenv('M3_M1_MODE', 'unavailable'),
                   m1_url=os.getenv('M3_M1_URL', ''), m1_token=os.getenv('M3_M1_TOKEN', ''),
                   assignment_hours=float(os.getenv('M3_ASSIGNMENT_SLA_HOURS', '24')),
                   repair_hours=float(os.getenv('M3_REPAIR_SLA_HOURS', '48')),
                   worker_interval=float(os.getenv('M3_WORKER_INTERVAL_SECONDS', '2')))
