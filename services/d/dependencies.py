"""D-02 consumer adapters for unavailable D-01 and M1 service credentials."""

from dataclasses import dataclass
import hmac
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from fastapi import Header

from services.platform import Problem


@dataclass(frozen=True)
class Identity:
    id: str
    department_id: str | None
    permissions: frozenset[str]

    @property
    def can_read_all(self) -> bool:
        return bool(self.permissions & {"room:manage", "operations:read"})


def identity_mode() -> str:
    # TEMPORARY-DEPENDENCY D02-IDENTITY：仅开发激活，按 development/README.md 随替身清理。
    if os.getenv("D_USE_DEV_IDENTITY") == "1":
        if os.getenv("APP_ENV") not in {"development", "test"}:
            raise Problem(503, "INVALID_DEPENDENCY_MODE", "Development identity is forbidden in this environment")
        return "development-substitute"
    return "real-http"


def bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer ") or not authorization[7:].strip():
        raise Problem(401, "AUTHENTICATION_REQUIRED", "A bearer token is required")
    return authorization[7:].strip()


def parse_identity(value) -> Identity:
    if (not isinstance(value, dict) or not isinstance(value.get("id"), str) or not value["id"].strip()
            or "departmentId" not in value
            or not (value["departmentId"] is None or isinstance(value["departmentId"], str) and value["departmentId"].strip())
            or not isinstance(value.get("permissions"), list)
            or not all(isinstance(p, str) and p for p in value["permissions"])):
        raise Problem(503, "IDENTITY_INVALID_RESPONSE", "Identity provider returned an invalid response")
    return Identity(value["id"], value["departmentId"], frozenset(value["permissions"]))


class NoIdentityRedirect(HTTPRedirectHandler):
    """Never forward user credentials to a redirected identity endpoint."""

    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def current_identity(authorization: str | None = Header(default=None)) -> Identity:
    token = bearer(authorization)
    # TEMPORARY-DEPENDENCY D02-IDENTITY：M1/D-02 消费 M2/D-01 的临时接入点。
    # M1/M2 可协调修改或替换；真实联调后按清单移除此分支，保留下方客户端与 D-02 权限校验。
    if identity_mode() == "development-substitute":
        from services.d.development.identity import identify
        value = identify(token)
        if value is None:
            raise Problem(401, "INVALID_IDENTITY", "Identity token is invalid")
        return parse_identity(value)
    base = os.getenv("D_IDENTITY_URL", "").rstrip("/")
    if not base:
        raise Problem(503, "IDENTITY_NOT_CONFIGURED", "Identity provider is not configured")
    if not base.startswith(("https://", "http://")):
        raise Problem(503, "IDENTITY_NOT_CONFIGURED", "Identity provider URL is invalid")
    # CONTRACT-ASSUMPTION D02-IDENTITY：路径/身份形状来自 contracts/d-dependencies.md v0.1.0 proposed。
    # 可由 M2/M1 按真实 D-01 契约协调修改；保留真实请求、parse_identity 和超时/拒绝处理。
    request = Request(base + "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    try:
        with build_opener(NoIdentityRedirect()).open(request, timeout=5) as response:
            # Bound responses so an unhealthy provider cannot exhaust the process.
            data = response.read(65537)
            if len(data) > 65536:
                raise Problem(503, "IDENTITY_INVALID_RESPONSE", "Identity response is too large")
            value = json.loads(data)
    except HTTPError as exc:
        if exc.code in {401, 403}:
            raise Problem(401, "INVALID_IDENTITY", "Identity token is invalid") from exc
        raise Problem(503, "IDENTITY_UNAVAILABLE", "Identity provider is unavailable") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise Problem(503, "IDENTITY_UNAVAILABLE", "Identity provider is unavailable") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise Problem(503, "IDENTITY_INVALID_RESPONSE", "Identity provider returned invalid JSON") from exc
    return parse_identity(value)


def require_admin(identity: Identity):
    if "room:manage" not in identity.permissions:
        raise Problem(403, "PERMISSION_DENIED", "room:manage permission is required")


def require_m1(authorization: str | None = Header(default=None)):
    expected = os.getenv("D_M1_TOKEN")
    if not expected:
        raise Problem(503, "SERVICE_AUTH_NOT_CONFIGURED", "M1 service credential is not configured")
    token = bearer(authorization)
    if not hmac.compare_digest(token.encode("utf-8"), expected.encode("utf-8")):
        raise Problem(401, "INVALID_SERVICE_CREDENTIAL", "M1 service credential is invalid")
