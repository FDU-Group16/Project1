"""Real M1 network adapter for m1-room-blocks.openapi.json@0.1.0-proposed."""

import json
import re
from http.client import HTTPException
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from .ports import GatewayFailure


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_receipt(source_id: str, payload: dict, receipt: dict) -> None:
    if not isinstance(receipt, dict):
        raise GatewayFailure('M1_INVALID_RECEIPT', False)
    expected = {**payload, 'sourceSystem': 'M3', 'sourceId': source_id}
    for key, value in expected.items():
        # bool must not masquerade as integer revision 1.
        if receipt.get(key) != value or type(receipt.get(key)) is not type(value):
            raise GatewayFailure('M1_RECEIPT_MISMATCH', False)
    if 'endsAt' not in payload and 'endsAt' in receipt:
        raise GatewayFailure('M1_RECEIPT_MISMATCH', False)
    if set(receipt) != set(expected) | {'appliedAt'}:
        raise GatewayFailure('M1_INVALID_RECEIPT', False)
    applied = receipt.get('appliedAt')
    try:
        if not isinstance(applied, str) or not re.fullmatch(
                r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z', applied):
            raise ValueError
        if datetime.fromisoformat(applied.replace('Z', '+00:00')).tzinfo is None:
            raise ValueError
    except ValueError:
        raise GatewayFailure('M1_INVALID_RECEIPT', False) from None


class HttpBlockGateway:
    def __init__(self, base_url: str, token: str, timeout: float = 3):
        parsed = urlsplit(base_url)
        if (parsed.scheme not in ('http', 'https') or not parsed.netloc
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError('M3_M1_URL must be an http(s) origin without credentials/query')
        if not token.strip() or '\n' in token or '\r' in token:
            raise ValueError('M3_M1_TOKEN is required and must be a single line')
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.timeout = timeout
        self.opener = build_opener(NoRedirect())

    def put(self, source_id: str, payload: dict, correlation_id: str) -> dict:
        url = f'{self.base_url}/internal/v1/room-blocks/m3/{quote(source_id, safe="")}'
        request = Request(url, data=json.dumps(payload).encode(), method='PUT', headers={
            'Content-Type': 'application/json', 'Authorization': f'Bearer {self.token}',
            'X-Correlation-Id': correlation_id,
        })
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                if response.status != 200:
                    raise GatewayFailure('M1_UNEXPECTED_STATUS', False)
                # Bound untrusted provider response size. Never log its body or token.
                raw = response.read(65537)
                if len(raw) > 65536:
                    raise GatewayFailure('M1_INVALID_RECEIPT', False)
                receipt = json.loads(raw)
        except HTTPError as exc:
            code = exc.code
            exc.close()
            raise GatewayFailure(f'M1_HTTP_{code}', code in (502, 503, 504)) from None
        except (URLError, TimeoutError, OSError, HTTPException):
            raise GatewayFailure('M1_NETWORK_UNAVAILABLE', True) from None
        except (ValueError, UnicodeError):
            raise GatewayFailure('M1_INVALID_RECEIPT', False) from None
        validate_receipt(source_id, payload, receipt)
        return receipt
