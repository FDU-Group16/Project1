"""Consumer-owned HTTP adapters. Production failures never fall back to synthetic data."""
import json
import os
import secrets
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

from fastapi import Header
from services.platform import Problem
from services.m1.masterdata import validate_room, validate_rooms


def dependency_mode():
    enabled = os.getenv('M1_USE_DEV_DEPENDENCIES') == '1'
    if enabled and os.getenv('APP_ENV') not in {'development', 'test'}:
        raise Problem(503, 'INVALID_DEPENDENCY_MODE', 'Development adapters require APP_ENV=development or test.')
    return 'development-substitutes' if enabled else 'real'


class NoDependencyRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward caller/service bearer credentials to a redirected origin.
        return None


def request_d(path, token, payload=None):
    if not token:
        raise Problem(503, 'DEPENDENCY_NOT_CONFIGURED', 'Required D credential is not configured.')
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request(os.getenv('D_BASE_URL', 'http://127.0.0.1:3104').rstrip('/') + path,
                  data=data, headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
    try:
        with build_opener(NoDependencyRedirect()).open(req, timeout=3) as response:
            result = json.load(response)
        if not isinstance(result, dict):
            raise ValueError('Invalid response')
        return result
    except HTTPError as exc:
        exc.close()
        if exc.code in (401, 403):
            raise Problem(exc.code, 'DEPENDENCY_AUTH_REJECTED', 'D rejected this identity or service credential.') from None
        if exc.code == 404 and path.startswith('/internal/v1/rooms/'):
            raise Problem(404, 'ROOM_NOT_FOUND', 'Room not found.') from None
        raise Problem(503, 'DEPENDENCY_UNAVAILABLE', 'D request failed; retry later.') from None
    except (URLError, TimeoutError, ValueError, OSError):
        raise Problem(503, 'DEPENDENCY_UNAVAILABLE', 'D is unavailable or returned invalid data.') from None


def identity(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith('Bearer ') or not authorization[7:]:
        raise Problem(401, 'UNAUTHORIZED', 'A bearer token is required.')
    token = authorization[7:]
    if dependency_mode() == 'development-substitutes':
        from services.m1.temporary_dependencies.adapters import development_identity
        return development_identity(token)
    result = request_d('/api/v1/auth/me', token)
    if (not isinstance(result.get('id'), str) or not result['id'] or 'departmentId' not in result
            or (result['departmentId'] is not None and not isinstance(result['departmentId'], str))
            or not isinstance(result.get('permissions'), list)
            or not all(isinstance(value,str) for value in result['permissions'])):
        raise Problem(503, 'INVALID_IDENTITY_RESPONSE', 'Identity provider returned an incompatible response.')
    return result


def require(identity_value, *permissions):
    if not any(permission in identity_value['permissions'] for permission in permissions):
        raise Problem(403, 'FORBIDDEN', 'Permission denied.')


def rooms():
    result = request_d('/internal/v1/rooms', os.getenv('D_M1_TOKEN'))
    return validate_rooms(result)


def room(room_id):
    result = request_d('/internal/v1/rooms/' + quote(room_id, safe=''), os.getenv('D_M1_TOKEN'))
    return validate_room(result,room_id)


def service_identity(source, authorization):
    configured = os.getenv(f'M1_{source}_TOKEN')
    if not configured:
        raise Problem(503, 'SERVICE_AUTH_NOT_CONFIGURED', 'Service identity is not configured.')
    other = 'M2' if source == 'M3' else 'M3'
    if os.getenv(f'M1_{other}_TOKEN') == configured:
        raise Problem(503, 'AMBIGUOUS_SERVICE_IDENTITY', 'M2 and M3 must use distinct service credentials.')
    token = authorization[7:] if authorization and authorization.startswith('Bearer ') else ''
    if not token:
        raise Problem(401, 'UNAUTHORIZED', 'Service bearer token required.')
    if not secrets.compare_digest(configured.encode(), token.encode()):
        other = 'M2' if source == 'M3' else 'M3'
        if os.getenv(f'M1_{other}_TOKEN') and secrets.compare_digest(os.environ[f'M1_{other}_TOKEN'].encode(), token.encode()):
            raise Problem(403, 'SOURCE_IDENTITY_MISMATCH', 'Service identity does not match source path.')
        raise Problem(401, 'UNAUTHORIZED', 'Invalid service identity.')


def deliver(kind, payload):
    if dependency_mode() == 'development-substitutes':
        from services.m1.temporary_dependencies.adapters import development_deliver
        development_deliver(kind, payload)
        return 'SIMULATED'
    path = '/internal/v1/notifications' if kind == 'notification' else '/internal/v1/audit'
    key = 'D_NOTIFICATION_TOKEN' if kind == 'notification' else 'D_AUDIT_TOKEN'
    result = request_d(path, os.getenv(key), payload)
    if result.get('eventId') != payload['eventId'] or result.get('status') not in {'accepted', 'delivered'}:
        raise Problem(503, 'INVALID_DELIVERY_RESPONSE', 'D did not acknowledge the event.')
    return 'DELIVERED' if result['status']=='delivered' else 'ACCEPTED'
