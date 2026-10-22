"""D-02 boundary validation. Business JSON uses camelCase."""

from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Name = Annotated[str, Field(strict=True, min_length=1, max_length=120)]
Department = Annotated[str, Field(strict=True, min_length=1, max_length=80)]
Number = Annotated[str, Field(strict=True, min_length=1, max_length=40)]
HourStart = Annotated[int, Field(strict=True, ge=0, le=23)]
HourEnd = Annotated[int, Field(strict=True, ge=1, le=24)]
Weekday = Annotated[int, Field(strict=True, ge=0, le=6)]
Weekdays = Annotated[list[Weekday], Field(min_length=1, max_length=7)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, strict=True)

    @field_validator("weekdays", check_fields=False)
    @classmethod
    def unique_weekdays(cls, value):
        if value is not None and len(set(value)) != len(value):
            raise ValueError("weekdays must be unique")
        return sorted(value) if value is not None else value

    @model_validator(mode="after")
    def valid_hours(self):
        start, end = getattr(self, "openHour", None), getattr(self, "closeHour", None)
        if start is not None and end is not None and start >= end:
            raise ValueError("openHour must precede closeHour")
        return self


class RoomCreate(Input):
    name: Name
    departmentId: Department | None = None
    openHour: HourStart
    closeHour: HourEnd
    weekdays: Weekdays
    active: bool = True


class Patch(Input):
    @model_validator(mode="after")
    def valid_patch(self):
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        for name in self.model_fields_set:
            if name != "departmentId" and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class RoomPatch(Patch):
    name: Name | None = None
    departmentId: Department | None = None
    openHour: HourStart | None = None
    closeHour: HourEnd | None = None
    weekdays: Weekdays | None = None
    active: bool | None = None


class SeatCreate(Input):
    number: Number
    hasSocket: bool = False
    active: bool = True


class SeatPatch(Patch):
    number: Number | None = None
    hasSocket: bool | None = None
    active: bool | None = None
