"""Consumer-owned boundaries. No imports from another business module."""

from typing import Protocol
from .models import Actor, DirectoryItem, Problem


class Directory(Protocol):
    def authenticate(self, token: str) -> Actor: ...
    def rooms(self, actor: Actor) -> list[DirectoryItem]: ...
    def technicians(self) -> list[DirectoryItem]: ...


class UnavailableDirectory:
    """D has no approved/implemented identity or room API yet; fail closed."""
    def authenticate(self, token: str) -> Actor:
        raise Problem(503, 'IDENTITY_UNAVAILABLE', '公共身份服务尚未接入，业务操作暂不可用。')

    def rooms(self, actor: Actor) -> list[DirectoryItem]:
        raise Problem(503, 'DIRECTORY_UNAVAILABLE', '空间主数据服务尚未接入。')

    def technicians(self) -> list[DirectoryItem]:
        raise Problem(503, 'DIRECTORY_UNAVAILABLE', '维修人员目录尚未接入。')


class BlockGateway(Protocol):
    def put(self, source_id: str, payload: dict, correlation_id: str) -> dict: ...


class GatewayFailure(Exception):
    def __init__(self, code: str, retryable: bool):
        super().__init__(code)
        self.code = code
        self.retryable = retryable


class UnavailableGateway:
    def put(self, source_id: str, payload: dict, correlation_id: str) -> dict:
        raise GatewayFailure('M1_NOT_CONFIGURED', False)
