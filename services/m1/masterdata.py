"""Strict consumer boundary for D-02 v0.1.0; additive provider fields are ignored.

This is a wire schema, not D business logic or a provider implementation.
"""
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from services.platform import Problem

StableId = Annotated[str, Field(min_length=1,max_length=128)]
Department = Annotated[str, Field(min_length=1,max_length=80)]
Weekday = Annotated[int, Field(ge=0,le=6)]


class WireModel(BaseModel):
    model_config = ConfigDict(strict=True,extra='ignore')

    @field_validator('id','roomId','departmentId',check_fields=False)
    @classmethod
    def stable_identifier(cls,value):
        if value is not None and (not value.strip() or value!=value.strip()):
            raise ValueError('Identifier must be nonblank without surrounding whitespace')
        return value

    @field_validator('name','number',check_fields=False)
    @classmethod
    def nonblank_text(cls,value):
        if not value.strip():
            raise ValueError('Text must not be blank')
        return value


class Seat(WireModel):
    id: StableId
    roomId: StableId
    number: str = Field(min_length=1,max_length=40)
    hasSocket: bool
    active: bool
    retired: bool

    @model_validator(mode='after')
    def retirement_state(self):
        if self.retired and self.active:
            raise ValueError('Retired seat cannot be active')
        return self


class RoomWithSeats(WireModel):
    id: StableId
    name: str = Field(min_length=1,max_length=120)
    departmentId: Department | None  # Required even when null: missing never means public.
    openHour: int = Field(ge=0,le=23)
    closeHour: int = Field(ge=1,le=24)
    weekdays: list[Weekday] = Field(min_length=1,max_length=7)
    active: bool
    retired: bool
    seats: list[Seat]

    @model_validator(mode='after')
    def consistent_room(self):
        if self.openHour>=self.closeHour or len(set(self.weekdays))!=len(self.weekdays):
            raise ValueError('Invalid opening schedule')
        if self.retired and self.active:
            raise ValueError('Retired room cannot be active')
        if len({seat.id for seat in self.seats})!=len(self.seats):
            raise ValueError('Duplicate stable seat ID')
        if len({seat.number for seat in self.seats})!=len(self.seats):
            raise ValueError('Duplicate seat number')
        if any(seat.roomId!=self.id for seat in self.seats):
            raise ValueError('Seat belongs to a different room')
        return self


class RoomList(WireModel):
    items: list[RoomWithSeats]

    @model_validator(mode='after')
    def unique_ids(self):
        if len({room.id for room in self.items})!=len(self.items):
            raise ValueError('Duplicate stable room ID')
        seats=[seat.id for room in self.items for seat in room.seats]
        if len(set(seats))!=len(seats):
            raise ValueError('Duplicate stable seat ID across rooms')
        return self


def invalid_master_data():
    return Problem(503,'INVALID_MASTER_DATA','D returned incompatible master data.')


def validate_room(value,expected_id):
    try:
        room=RoomWithSeats.model_validate(value)
        if room.id!=expected_id:
            raise invalid_master_data()
        return room.model_dump()
    except ValidationError:
        raise invalid_master_data() from None


def validate_rooms(value):
    try:
        return RoomList.model_validate(value).model_dump()['items']
    except ValidationError:
        raise invalid_master_data() from None
