"""Network-only consumer of m1-room-blocks.openapi.json@0.2.0-proposed."""
from datetime import datetime
import json
import re
from urllib.parse import urlsplit
import httpx


class SyncFailure(Exception):
    def __init__(self, message, retryable):
        self.message, self.retryable = message, retryable
        super().__init__(message)


def utc_timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", value
    ):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def validate_receipt(receipt, source_id, payload):
    expected = {"sourceSystem": "M3", "sourceId": source_id, **payload}
    if not isinstance(receipt, dict) or set(receipt) != set(expected) | {"appliedAt"}:
        raise SyncFailure("M1 回执字段不符合契约", False)
    if type(receipt.get("revision")) is not int:
        raise SyncFailure("M1 回执版本类型无效", False)
    if any(receipt[k] != v for k, v in expected.items()):
        raise SyncFailure("M1 回执与目标状态不一致", False)
    if not all(utc_timestamp(receipt[k]) for k in ("startsAt", "appliedAt")):
        raise SyncFailure("M1 回执 UTC 时间无效", False)
    if "endsAt" in receipt and (
        not utc_timestamp(receipt["endsAt"]) or
        datetime.fromisoformat(receipt["endsAt"].replace("Z", "+00:00")) <=
        datetime.fromisoformat(receipt["startsAt"].replace("Z", "+00:00"))
    ):
        raise SyncFailure("M1 回执结束时间无效", False)
    return receipt


class M1Client:
    def __init__(self, base_url, token, timeout=3, transport=None):
        self.base_url, self.token, self.timeout, self.transport = base_url.rstrip("/"), token, timeout, transport

    def apply(self, source_id, payload, correlation_id):
        try:
            parts = urlsplit(self.base_url)
            parts.port  # Reject malformed/non-numeric/out-of-range ports before claiming a network failure.
        except ValueError:
            raise SyncFailure("M1 服务地址格式无效", False) from None
        if (parts.scheme not in {"http", "https"} or not parts.netloc or parts.username or parts.password
                or parts.query or parts.fragment or not self.token
                or any(ord(char) < 33 or ord(char) > 126 for char in self.token)):
            raise SyncFailure("M1 服务地址或服务凭据未配置", False)
        if not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", source_id):
            raise SyncFailure("M1 来源 ID 不符合契约", False)
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=False, transport=self.transport,
                              trust_env=False) as client:
                with client.stream("PUT", f"{self.base_url}/internal/v1/room-blocks/m3/{source_id}",
                    json=payload, headers={"Authorization": f"Bearer {self.token}",
                                           "X-Correlation-Id": correlation_id}) as response:
                    if response.status_code != 200:
                        raise SyncFailure(f"M1 写回返回 HTTP {response.status_code}",
                                          response.status_code in {502, 503, 504})
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > 65536:
                            raise SyncFailure("M1 回执超过大小限制", False)
                        chunks.append(chunk)
                    try:
                        def unique_object(pairs):
                            result = {}
                            for key, value in pairs:
                                if key in result:
                                    raise ValueError("Duplicate key")
                                result[key] = value
                            return result
                        receipt = json.loads(b"".join(chunks), object_pairs_hook=unique_object)
                    except (ValueError, UnicodeError):
                        raise SyncFailure("M1 回执不是有效 JSON", False) from None
        except httpx.RequestError:
            raise SyncFailure("M1 网络异常或请求超时", True) from None
        except httpx.InvalidURL:
            raise SyncFailure("M1 服务地址格式无效", False) from None
        return validate_receipt(receipt, source_id, payload)
