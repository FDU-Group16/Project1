"""Consumer adapter checks against a tiny HTTP identity provider; not D-01 tests."""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from threading import Thread
import unittest
from unittest.mock import patch

from services.d.dependencies import current_identity, identity_mode
from services.platform import Problem


@contextmanager
def provider(status, payload):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.server.seen_path = self.path
            self.server.seen_auth = self.headers.get("Authorization")
            self.send_response(status)
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with patch.dict(os.environ, {"D_USE_DEV_IDENTITY": "0", "D_IDENTITY_URL": f"http://127.0.0.1:{server.server_port}"}):
            yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class IdentityAdapterTests(unittest.TestCase):
    def test_real_http_adapter_forwards_token_and_parses_permission_scope(self):
        with provider(200, {"id": "synthetic-user", "departmentId": "cs", "permissions": ["seat:reserve"]}) as server:
            identity = current_identity("Bearer synthetic-token")
            self.assertEqual(identity.id, "synthetic-user")
            self.assertEqual(identity.department_id, "cs")
            self.assertFalse(identity.can_read_all)
            self.assertEqual(server.seen_path, "/api/v1/auth/me")
            self.assertEqual(server.seen_auth, "Bearer synthetic-token")

    def test_failed_or_malformed_provider_never_falls_back(self):
        for status, payload, expected in [(401, {}, 401), (500, {}, 503), (200, {"id": "bad"}, 503),
                                          (200, {"id": "bad", "departmentId": 42, "permissions": ["room:manage"]}, 503)]:
            with provider(status, payload):
                with self.assertRaises(Problem) as result:
                    current_identity("Bearer dev-room-admin")
                self.assertEqual(result.exception.status, expected)

    def test_explicit_substitute_and_production_rejection(self):
        with patch.dict(os.environ, {"APP_ENV": "production", "D_USE_DEV_IDENTITY": "1"}):
            with self.assertRaises(Problem) as result:
                identity_mode()
            self.assertEqual(result.exception.status, 503)
        with patch.dict(os.environ, {"APP_ENV": "test", "D_USE_DEV_IDENTITY": "1"}):
            self.assertEqual(identity_mode(), "development-substitute")
            self.assertIn("room:manage", current_identity("Bearer dev-room-admin").permissions)
            with self.assertRaises(Problem) as result:
                current_identity("Bearer unknown")
            self.assertEqual(result.exception.status, 401)

    def test_missing_real_provider_is_unavailable(self):
        with patch.dict(os.environ, {"D_USE_DEV_IDENTITY": "0", "D_IDENTITY_URL": ""}):
            with self.assertRaises(Problem) as result:
                current_identity("Bearer dev-room-admin")
            self.assertEqual(result.exception.status, 503)


if __name__ == "__main__":
    unittest.main()
