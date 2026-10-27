"""Real D HTTP consumer; failures never select a development identity.

CONTRACT-ASSUMPTION M3-D-DEV: repair permissions/technician endpoint are a
consumer proposal in contracts/m3-directory-dependencies.md, not a D-01 provider.
"""
import json
from urllib.parse import urlsplit
import httpx
from .ports import Actor


class DirectoryFailure(Exception):
    def __init__(self, code, message, status=503):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def valid_base_url(value):
    try:
        parsed = urlsplit(value)
        parsed.port
    except (TypeError, ValueError):
        return False
    return bool(parsed.scheme in {"http", "https"} and parsed.hostname
                and not parsed.username and not parsed.password and not parsed.query
                and not parsed.fragment and all(33 <= ord(c) <= 126 for c in value))


def text_field(value, maximum=128):
    return isinstance(value, str) and bool(value.strip()) and value == value.strip() and len(value) <= maximum


def invalid_response():
    return DirectoryFailure("DEPENDENCY_INVALID_RESPONSE", "身份或目录服务返回的数据不符合契约")


def identity_record(value, bearer=""):
    if (not isinstance(value, dict) or not text_field(value.get("id"))
            or not text_field(value.get("displayName"), 200)
            or "departmentId" not in value
            or value["departmentId"] is not None and not text_field(value["departmentId"])
            or not isinstance(value.get("permissions"), list) or len(value["permissions"]) > 100
            or not all(text_field(p) for p in value["permissions"])):
        raise invalid_response()
    permissions = frozenset(value["permissions"])
    role = ("admin" if "repair:dispatch" in permissions else
            "technician" if "repair:work" in permissions else
            "reporter" if permissions & {"repair:report", "seat:reserve"} else "unavailable")
    return Actor(value["id"], value["displayName"], role, permissions, value["departmentId"], bearer)


class HttpDirectory:
    def __init__(self, identity_base_url, d_base_url, timeout=3, *, transport=None):
        self.identity_base_url, self.d_base_url = identity_base_url.rstrip("/"), d_base_url.rstrip("/")
        self.timeout, self.transport = timeout, transport

    @property
    def configured(self):
        return valid_base_url(self.identity_base_url) and valid_base_url(self.d_base_url)

    def _get(self, base_url, path, bearer):
        if not self.configured:
            raise DirectoryFailure("DEPENDENCY_UNAVAILABLE", "正式身份与房间目录地址未配置")
        if not bearer or len(bearer) > 4096 or not all(33 <= ord(c) <= 126 for c in bearer):
            raise DirectoryFailure("UNAUTHENTICATED", "身份凭据无效", 401)
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=False, trust_env=False,
                              transport=self.transport) as client:
                with client.stream("GET", base_url + path, headers={"Authorization": f"Bearer {bearer}"}) as response:
                    if response.status_code == 401:
                        raise DirectoryFailure("UNAUTHENTICATED", "身份无效或已过期", 401)
                    if response.status_code == 403:
                        raise DirectoryFailure("FORBIDDEN", "当前身份无权访问所需目录", 403)
                    if response.status_code != 200:
                        raise DirectoryFailure("DEPENDENCY_UNAVAILABLE", "身份或目录服务暂不可用")
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > 1048576:
                            raise invalid_response()
                        chunks.append(chunk)
                    def unique_object(pairs):
                        result = {}
                        for key, value in pairs:
                            if key in result:
                                raise ValueError("Duplicate JSON key")
                            result[key] = value
                        return result
                    try:
                        return json.loads(b"".join(chunks), object_pairs_hook=unique_object)
                    except (ValueError, UnicodeError):
                        raise invalid_response() from None
        except (httpx.RequestError, httpx.InvalidURL):
            raise DirectoryFailure("DEPENDENCY_UNAVAILABLE", "身份或目录服务不可达或请求超时") from None

    def authenticate(self, token):
        return identity_record(self._get(self.identity_base_url, "/api/v1/auth/me", token), token)

    @staticmethod
    def _items(data):
        if not isinstance(data, dict) or not isinstance(data.get("items"), list) or len(data["items"]) > 5000:
            raise invalid_response()
        return data["items"]

    def rooms(self, actor):
        # The public D-02 endpoint applies the current user's department scope.
        # Never substitute D_M1_TOKEN or a privileged service token here.
        rows = self._items(self._get(self.d_base_url, "/api/v1/rooms", actor.bearer))
        items, seen = [], set()
        for row in rows:
            if (not isinstance(row, dict) or not text_field(row.get("id"))
                    or not text_field(row.get("name"), 200)
                    or type(row.get("active")) is not bool or type(row.get("retired")) is not bool
                    or row["id"] in seen):
                raise invalid_response()
            seen.add(row["id"])
            if row["active"] and not row["retired"]:
                items.append({"id": row["id"], "name": row["name"]})
        return items

    def technicians(self, actor):
        if not actor.can("dispatch"):
            raise DirectoryFailure("FORBIDDEN", "仅维修管理员可查看维修人员目录", 403)
        rows = self._items(self._get(self.identity_base_url, "/api/v1/repair-technicians", actor.bearer))
        result, seen = [], set()
        for row in rows:
            if not isinstance(row, dict):
                raise invalid_response()
            candidate = identity_record({"departmentId": None, **row})
            if not candidate.can("work") or candidate.id in seen:
                raise invalid_response()
            seen.add(candidate.id)
            # The roster role describes eligibility; the next user request is
            # independently authenticated and may carry several permissions.
            result.append(Actor(candidate.id, candidate.name, "technician", candidate.permissions,
                                candidate.department_id))
        return result
