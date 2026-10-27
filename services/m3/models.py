"""M3 public models. Identity is always obtained from a trusted provider."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

Category = Literal['electrical', 'plumbing', 'furniture', 'network', 'other']
Status = Literal['REPORTED', 'ASSIGNED', 'STARTING_REPAIR', 'IN_PROGRESS',
                 'PENDING_ACCEPTANCE', 'ACCEPTING', 'CLOSED', 'CANCELLED']


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError('A timezone-aware clock is required')
    return value.astimezone(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class CreateOrder(Input):
    roomId: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)
    category: Category


class Command(Input):
    version: StrictInt = Field(ge=1)


class Assign(Command):
    assigneeId: str = Field(min_length=1, max_length=128)


class Complete(Command):
    resolution: str = Field(min_length=1, max_length=2000)


class Reason(Command):
    reason: str = Field(min_length=1, max_length=1000)


class Rate(Command):
    rating: StrictInt = Field(ge=1, le=5)
    comment: str = Field(default='', max_length=1000)


class Actor(BaseModel):
    id: str
    name: str
    roles: list[str]


class DirectoryItem(BaseModel):
    id: str
    name: str


class DirectoryList(BaseModel):
    items: list[DirectoryItem]


class HistoryItem(BaseModel):
    action: str
    actorId: str
    at: str
    detail: str


class WorkOrder(BaseModel):
    id: str
    roomId: str
    roomName: str
    title: str
    description: str
    category: Category
    reporterId: str
    assigneeId: str | None
    status: Status
    version: int
    createdAt: str
    updatedAt: str
    dueAt: str | None
    escalated: bool
    rating: int | None
    comment: str | None
    resolution: str | None
    syncStatus: Literal['NONE', 'PENDING', 'SYNCED', 'FAILED']
    syncError: str | None
    history: list[HistoryItem]


class OrderList(BaseModel):
    items: list[WorkOrder]


class Context(BaseModel):
    mode: Literal['unconfigured', 'development', 'production']
    dependencyMode: Literal['unavailable', 'stub', 'http']
    message: str


class Problem(Exception):
    def __init__(self, status: int, code: str, detail: str):
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail
