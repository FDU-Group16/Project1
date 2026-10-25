"""Application input boundary tests; no HTTP, identity or database substitute."""

import json
from pathlib import Path
import unittest

from pydantic import ValidationError

from services.m2.contracts import ApplicationCreate


def valid_input():
    return {
        "room_id": "D/room-001",
        "start_at": "2026-10-29T02:00:00Z",
        "end_at": "2026-10-29T03:00:00Z",
        "purpose": "  课程讨论  ",
        "attendee_count": 6,
    }


class ApplicationInputTests(unittest.TestCase):
    def test_json_roundtrip_and_trim(self):
        request = ApplicationCreate.model_validate_json(json.dumps(valid_input()))
        expected = valid_input() | {"purpose": "课程讨论"}
        self.assertEqual(request.model_dump(mode="json"), expected)
        self.assertEqual(ApplicationCreate.model_validate_json(request.model_dump_json()), request)
        self.assertEqual(request.time_range.starts_at, request.start_at)
        self.assertEqual(request.time_range.ends_at, request.end_at)

    def test_missing_fields(self):
        for key in valid_input():
            data = valid_input()
            del data[key]
            with self.subTest(field=key), self.assertRaises(ValidationError):
                ApplicationCreate.model_validate(data)

    def test_client_cannot_supply_identity_or_approval_fields(self):
        for key in ("applicant_id", "department_id", "permission_codes", "status",
                    "deadline_at", "version", "unexpected"):
            with self.subTest(field=key), self.assertRaises(ValidationError):
                ApplicationCreate.model_validate(valid_input() | {key: "forged"})

    def test_count_requires_positive_integer(self):
        for bad in (0, -1, True, False, "6", 6.0, 1.5, None):
            with self.subTest(value=bad), self.assertRaises(ValidationError):
                ApplicationCreate.model_validate(valid_input() | {"attendee_count": bad})
        self.assertEqual(ApplicationCreate.model_validate(valid_input() | {"attendee_count": 1}).attendee_count, 1)

    def test_room_id_is_opaque_nonempty_string(self):
        for room in ("room/001", "Case-Sensitive", "  D-id  "):
            self.assertEqual(ApplicationCreate.model_validate(valid_input() | {"room_id": room}).room_id, room)
        for bad in ("", 1, None, True):
            with self.subTest(value=bad), self.assertRaises(ValidationError):
                ApplicationCreate.model_validate(valid_input() | {"room_id": bad})

    def test_purpose_bounds_apply_after_trimming(self):
        for text in ("a", "论" * 500):
            request = ApplicationCreate.model_validate(valid_input() | {"purpose": "  " + text + " \n"})
            self.assertEqual(request.purpose, text)
        for bad in ("", " \t\n", "论" * 501, 1, None):
            with self.subTest(value=bad), self.assertRaises(ValidationError):
                ApplicationCreate.model_validate(valid_input() | {"purpose": bad})

    def test_timestamps_are_explicit_utc_strings(self):
        for key in ("start_at", "end_at"):
            for bad in ("2026-10-29T02:00:00", "2026-10-29T02:00:00+00:00",
                        "2026-10-29T10:00:00+08:00", "2026-10-29", "2026-02-30T02:00:00Z",
                        "2026-10-29T25:00:00Z", "2026-10-29 02:00:00Z", 1793239200, None):
                with self.subTest(field=key, value=bad), self.assertRaises(ValidationError):
                    ApplicationCreate.model_validate(valid_input() | {key: bad})

    def test_fractional_seconds_and_interval_order(self):
        data = valid_input() | {"start_at": "2026-10-29T02:00:00.123456Z"}
        self.assertEqual(ApplicationCreate.model_validate(data).start_at.microsecond, 123456)
        for end in (data["start_at"], "2026-10-29T02:00:00.123455Z"):
            with self.subTest(end=end), self.assertRaises(ValidationError):
                ApplicationCreate.model_validate(data | {"end_at": end})

    def test_validated_input_cannot_be_assigned_new_claims(self):
        request = ApplicationCreate.model_validate(valid_input())
        with self.assertRaises(ValidationError):
            request.attendee_count = 0

    def test_no_unapproved_availability_or_future_policy(self):
        # This DTO cannot approve an application or determine room capacity.
        data = valid_input() | {"start_at": "2000-01-01T01:00:00Z", "end_at": "2000-01-01T02:00:00Z"}
        self.assertEqual(ApplicationCreate.model_validate(data).start_at.year, 2000)

    def test_schema_matches_existing_public_input_shape(self):
        root = Path(__file__).resolve().parents[3]
        schemas = json.loads((root / "contracts/m2.openapi.json").read_text())["components"]["schemas"]
        public = schemas["ApplicationCreate"]
        generated = ApplicationCreate.model_json_schema()
        self.assertEqual(set(generated["required"]), set(public["required"]))
        self.assertEqual(set(generated["properties"]), set(public["properties"]))
        self.assertEqual(generated["additionalProperties"], public["additionalProperties"])
        for name in public["properties"]:
            expected = public["properties"][name]
            if "$ref" in expected:
                expected = schemas[expected["$ref"].split("/")[-1]]
            for key in ("type", "format", "minLength", "maxLength", "minimum", "pattern"):
                if key in expected:
                    self.assertEqual(generated["properties"][name].get(key), expected[key], (name, key))


if __name__ == "__main__":
    unittest.main()
