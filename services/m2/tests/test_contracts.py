"""Pure value-type tests: synthetic data, no services or database substitutes."""

import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

from services.m2.contracts import Actor, TimeRange


class ActorTests(unittest.TestCase):
    def test_empty_claims_do_not_grant_global_scope(self):
        actor = Actor(user_id="test-user")
        self.assertEqual(actor.permission_codes, frozenset())
        self.assertEqual(actor.managed_department_ids, frozenset())
        self.assertEqual(actor.managed_room_ids, frozenset())
        self.assertFalse(actor.manage_all_departments)
        self.assertFalse(actor.manage_all_rooms)

    def test_claim_sets_are_snapshots(self):
        for name in ("permission_codes", "managed_department_ids", "managed_room_ids"):
            with self.subTest(name=name):
                claims = {"original"}
                actor = Actor(user_id="test-user", **{name: claims})
                claims.add("added-later")
                self.assertEqual(getattr(actor, name), frozenset({"original"}))
                self.assertIsInstance(getattr(actor, name), frozenset)

    def test_frozen_identity_and_explicit_global_flag(self):
        actor = Actor(user_id="test-user", manage_all_rooms=True)
        self.assertTrue(actor.manage_all_rooms)
        with self.assertRaises(FrozenInstanceError):
            actor.user_id = "different-user"
        with self.assertRaises(FrozenInstanceError):
            actor.manage_all_departments = True

    def test_external_ids_are_not_normalized(self):
        actor = Actor(user_id="Case-Sensitive", department_id="dept/01")
        self.assertEqual(actor.user_id, "Case-Sensitive")
        self.assertEqual(actor.department_id, "dept/01")

    def test_invalid_claims_are_rejected(self):
        for name in ("user_id", "department_id"):
            for bad in ("", "  ", 1, True):
                with self.subTest(name=name, bad=bad), self.assertRaises(ValueError):
                    Actor(**{"user_id": "test-user", name: bad})
        with self.assertRaises(ValueError):
            Actor(user_id=None)
        for name in ("permission_codes", "managed_department_ids", "managed_room_ids"):
            for bad in ("room-1", ["room-1"], {""}, {1}, None):
                with self.subTest(name=name, bad=bad), self.assertRaises(ValueError):
                    Actor(user_id="test-user", **{name: bad})

    def test_flags_are_not_truthy_strings_or_numbers(self):
        for name in ("manage_all_rooms", "manage_all_departments"):
            for bad in ("false", "true", 1, 0, None):
                with self.subTest(name=name, bad=bad), self.assertRaises(ValueError):
                    Actor(user_id="test-user", **{name: bad})


class NoOffset(tzinfo):
    def utcoffset(self, dt):
        return None


class TimeRangeTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 10, 29, 2, tzinfo=UTC)
        self.end = self.start + timedelta(hours=1)
        self.slot = TimeRange(self.start, self.end)

    def test_equivalent_offsets_normalize_to_utc(self):
        offset = timezone(timedelta(hours=8))
        local = TimeRange(self.start.astimezone(offset), self.end.astimezone(offset))
        self.assertEqual(local, self.slot)
        self.assertIs(local.starts_at.tzinfo, UTC)
        self.assertIs(local.ends_at.tzinfo, UTC)

    def test_both_endpoints_require_an_actual_offset(self):
        for bad in (self.start.replace(tzinfo=None), self.start.replace(tzinfo=NoOffset()),
                    "2026-10-29T02:00:00Z", None):
            with self.subTest(endpoint="start", bad=bad), self.assertRaises(ValueError):
                TimeRange(bad, self.end)
            with self.subTest(endpoint="end", bad=bad), self.assertRaises(ValueError):
                TimeRange(self.start, bad)

    def test_equal_and_reversed_intervals_are_rejected(self):
        for end in (self.start, self.start - timedelta(microseconds=1)):
            with self.subTest(end=end), self.assertRaises(ValueError):
                TimeRange(self.start, end)

    def test_validation_compares_instants_not_wall_clock(self):
        # Local end reads 09:30, but is earlier in UTC than the 02:00Z start.
        end = datetime(2026, 10, 29, 9, 30, tzinfo=timezone(timedelta(hours=8)))
        with self.assertRaises(ValueError):
            TimeRange(self.start, end)

    def test_adjacent_and_disjoint_intervals_do_not_overlap(self):
        for other in (TimeRange(self.end, self.end + timedelta(hours=1)),
                      TimeRange(self.start - timedelta(hours=1), self.start),
                      TimeRange(self.end + timedelta(hours=1), self.end + timedelta(hours=2))):
            with self.subTest(other=other):
                self.assertFalse(self.slot.overlaps(other))
                self.assertFalse(other.overlaps(self.slot))

    def test_partial_contained_and_identical_intervals_overlap(self):
        for other in (self.slot,
                      TimeRange(self.start + timedelta(minutes=15), self.end),
                      TimeRange(self.start - timedelta(hours=1), self.end + timedelta(hours=1)),
                      TimeRange(self.end - timedelta(microseconds=1), self.end + timedelta(hours=1))):
            with self.subTest(other=other):
                self.assertTrue(self.slot.overlaps(other))
                self.assertTrue(other.overlaps(self.slot))

    def test_dst_fold_is_ordered_by_utc(self):
        zone = ZoneInfo("America/New_York")
        # During rollback, 01:15 fold=1 is later than 01:45 fold=0.
        start = datetime(2026, 11, 1, 1, 45, tzinfo=zone, fold=0)
        end = datetime(2026, 11, 1, 1, 15, tzinfo=zone, fold=1)
        interval = TimeRange(start, end)
        self.assertEqual(interval.ends_at - interval.starts_at, timedelta(minutes=30))
        with self.assertRaises(ValueError):
            TimeRange(end, start)

    def test_interval_is_immutable_and_requires_interval_operand(self):
        with self.assertRaises(FrozenInstanceError):
            self.slot.ends_at = self.start
        with self.assertRaises(TypeError):
            self.slot.overlaps(None)


if __name__ == "__main__":
    unittest.main()
