"""Retry fingerprint behavior with synthetic input and no database substitute."""

from dataclasses import FrozenInstanceError, replace
import json
import subprocess
import sys
import unittest

from pydantic import ValidationError

from services.m2.contracts import ApplicationCreate
from services.m2.idempotency import IdempotencyScope, application_input_digest


def payload():
    return dict(room_id="D/room-001", start_at="2026-10-29T02:00:00Z",
                end_at="2026-10-29T03:00:00Z", purpose="课程讨论", attendee_count=6)


def fingerprint(data):
    return application_input_digest(ApplicationCreate.model_validate(data))


class IdempotencyTests(unittest.TestCase):
    def test_equivalent_input_has_same_digest(self):
        data = payload()
        reordered = dict(reversed(list(data.items())))
        reordered.update(purpose=" \t课程讨论\n", start_at="2026-10-29T02:00:00.000Z")
        self.assertEqual(fingerprint(data), fingerprint(reordered))

    def test_every_business_field_affects_digest(self):
        original = fingerprint(payload())
        changes = dict(room_id="D/room-002", start_at="2026-10-29T02:00:01Z",
                       end_at="2026-10-29T03:00:01Z", purpose="小组讨论", attendee_count=7)
        for name, value in changes.items():
            with self.subTest(field=name):
                self.assertNotEqual(original, fingerprint(payload() | {name: value}))

    def test_opaque_room_id_and_internal_purpose_whitespace_preserved(self):
        original = fingerprint(payload())
        for change in ({"room_id": " D/room-001"}, {"room_id": "d/room-001"},
                       {"purpose": "课程 讨论"}):
            with self.subTest(change=change):
                self.assertNotEqual(original, fingerprint(payload() | change))

    def test_digest_is_versioned_and_stable_across_processes(self):
        expected = fingerprint(payload())
        self.assertRegex(expected, r"^m2\.application-create\.v1:sha256:[0-9a-f]{64}$")
        code = ("import sys; from services.m2.contracts import ApplicationCreate; "
                "from services.m2.idempotency import application_input_digest; "
                "print(application_input_digest(ApplicationCreate.model_validate_json(sys.stdin.read())))")
        result = subprocess.run([sys.executable, "-c", code], input=json.dumps(payload()),
                                capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), expected)

    def test_rejects_unvalidated_dictionary(self):
        with self.assertRaises(TypeError):
            application_input_digest(payload())

    def test_revalidates_bypassed_model(self):
        request = ApplicationCreate.model_validate(payload())
        with self.assertRaises(ValidationError):
            application_input_digest(request.model_copy(update={"attendee_count": 0}))
        with self.assertRaises(ValidationError):
            application_input_digest(ApplicationCreate.model_construct(**(payload() | {"purpose": " "})))

    def test_scope_separates_users_actions_targets_and_keys(self):
        scope = IdempotencyScope("user-a", "create", "/applications", "retry-1")
        for field, value in dict(user_id="user-b", action="withdraw", target="/applications/1", key="retry-2").items():
            with self.subTest(field=field):
                self.assertNotEqual(scope.storage_key, replace(scope, **{field: value}).storage_key)
        self.assertEqual(scope, IdempotencyScope(*scope.storage_key))

    def test_structured_scope_avoids_delimiter_collision(self):
        left = IdempotencyScope("user:a", "create", "applications", "k")
        right = IdempotencyScope("user", "a:create", "applications", "k")
        self.assertEqual(":".join(left.storage_key), ":".join(right.storage_key))
        self.assertNotEqual(left.storage_key, right.storage_key)

    def test_scope_is_immutable_and_preserves_opaque_key(self):
        scope = IdempotencyScope("u", "create", "applications", " Key ")
        self.assertEqual(scope.key, " Key ")
        self.assertNotEqual(scope, replace(scope, key="key"))
        with self.assertRaises(FrozenInstanceError):
            scope.key = "changed"

    def test_scope_rejects_missing_or_nonstring_parts(self):
        scope = IdempotencyScope("u", "create", "applications", "k")
        for field in ("user_id", "action", "target", "key"):
            for invalid in ("", None, 1, True):
                with self.subTest(field=field, value=invalid), self.assertRaises(ValueError):
                    replace(scope, **{field: invalid})


if __name__ == "__main__":
    unittest.main()
