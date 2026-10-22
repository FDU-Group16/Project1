"""Prove critical behavior tests reject deliberate in-memory regressions.

No source files are changed. Run only inside the disposable business test DB.
"""
import io
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
from unittest.mock import patch

from services.m1 import core
from services.m1.tests.test_behavior import M1Behavior


def run_case(method):
    return unittest.TextTestRunner(stream=io.StringIO()).run(unittest.TestSuite([M1Behavior(method)]))


for target, replacement, method in (
    ('authorized_room', lambda room, user: True, 'test_m101_department_filter_and_direct_booking_denial'),
    ('ensure_no_conflict', lambda *args: None, 'test_m103_concurrent_seat_and_user_conflicts'),
):
    with patch.object(core, target, replacement):
        result = run_case(method)
        if result.errors or not result.failures or result.skipped:
            raise AssertionError(f'Mutation {target} did not produce the expected assertion failure')
    restored = run_case(method)
    if not restored.wasSuccessful() or restored.skipped:
        raise AssertionError(f'Restored behavior failed: {method}')
    print(f'PASS mutation: breaking {target} fails {method}; restoring it passes.')
