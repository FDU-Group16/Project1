"""Shared M2 value types; no authentication, approval policy or persistence.

Actor must be constructed by a trusted identity adapter, never directly from
browser-supplied permissions. These types are only part of M2-BASE.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime


def _identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    # External identifiers are opaque: validation must not rewrite them.
    return value


def _identifier_set(value: frozenset[str], name: str) -> frozenset[str]:
    if not isinstance(value, (set, frozenset)):
        raise ValueError(f"{name} must be a set of strings")
    return frozenset(_identifier(item, name) for item in value)


@dataclass(frozen=True, slots=True)
class Actor:
    """Immutable snapshot of identity claims, not proof of authentication."""

    user_id: str
    permission_codes: frozenset[str] = field(default_factory=frozenset)
    department_id: str | None = None
    managed_department_ids: frozenset[str] = field(default_factory=frozenset)
    managed_room_ids: frozenset[str] = field(default_factory=frozenset)
    manage_all_departments: bool = False
    manage_all_rooms: bool = False

    def __post_init__(self) -> None:
        _identifier(self.user_id, "user_id")
        if self.department_id is not None:
            _identifier(self.department_id, "department_id")
        for name in (
            "permission_codes", "managed_department_ids", "managed_room_ids"
        ):
            object.__setattr__(self, name, _identifier_set(getattr(self, name), name))
        for name in ("manage_all_departments", "manage_all_rooms"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be a boolean")


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class TimeRange:
    """Non-empty half-open interval [starts_at, ends_at), normalized to UTC.

    This checks interval geometry only. Availability, future-time requirements
    and approval deadlines belong to the use case and its confirmed policies.
    """

    starts_at: datetime
    ends_at: datetime

    def __post_init__(self) -> None:
        start = _utc(self.starts_at, "starts_at")
        end = _utc(self.ends_at, "ends_at")
        if start >= end:
            raise ValueError("ends_at must be later than starts_at")
        object.__setattr__(self, "starts_at", start)
        object.__setattr__(self, "ends_at", end)

    def overlaps(self, other: "TimeRange") -> bool:
        """Whether two intervals share time; touching endpoints do not."""
        if not isinstance(other, TimeRange):
            raise TypeError("other must be a TimeRange")
        return self.starts_at < other.ends_at and other.starts_at < self.ends_at
