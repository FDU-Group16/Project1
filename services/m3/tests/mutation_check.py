"""Kill representative mutants in disposable copies; never edit working code.

Run from the repository root: .venv/bin/python services/m3/tests/mutation_check.py
"""

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
MUTANTS = [
    (
        'reporter authorization bypass',
        "if order['reporterId'] != actor.id:",
        'if False:  # deliberate mutation',
        'test_visibility_and_permissions_enforced_by_service',
    ),
    (
        'release on completion before acceptance',
        "order['status'], order['resolution'] = 'PENDING_ACCEPTANCE', body['resolution']",
        "order['status'], order['resolution'] = 'PENDING_ACCEPTANCE', body['resolution']\n"
        "                self._enqueue(connection, order, 'RELEASED', now)",
        'test_complete_reject_accept_rate_lifecycle_preserves_block_until_accept',
    ),
    (
        'remove SLA escalation deduplication',
        "and order['dueAt'] is not None and order['dueAt'] <= now and not order['escalated']",
        "and order['dueAt'] is not None and order['dueAt'] <= now",
        'test_sla_exact_boundary_and_reassignment_cannot_postpone',
    ),
]


def run(directory, method):
    return subprocess.run(
        [sys.executable, '-m', 'unittest',
         'services.m3.tests.test_work_orders.WorkOrderTests.' + method],
        cwd=directory, capture_output=True, text=True, timeout=30,
    )


for name, before, after, method in MUTANTS:
    with tempfile.TemporaryDirectory(prefix='m3-mutation-') as temporary:
        directory = Path(temporary)
        shutil.copytree(ROOT / 'services', directory / 'services',
                        ignore=shutil.ignore_patterns('__pycache__', '*.db', '*.sqlite3'))
        baseline = run(directory, method)
        if baseline.returncode != 0:
            raise RuntimeError(f'Baseline failed for {name}:\n{baseline.stderr}')
        target = directory / 'services/m3/service.py'
        source = target.read_text()
        if source.count(before) != 1:
            raise RuntimeError(f'Mutation target no longer unique: {name}')
        target.write_text(source.replace(before, after))
        # Avoid timestamp-resolution bytecode reuse in the disposable copy.
        for cache in directory.rglob('__pycache__'):
            shutil.rmtree(cache)
        result = run(directory, method)
        if result.returncode == 0:
            raise RuntimeError(f'Mutant survived: {name}')
        if 'FAIL:' not in result.stderr and 'ERROR:' not in result.stderr:
            raise RuntimeError(f'Mutant did not fail through unittest: {result.stderr}')
        print(f'KILLED: {name} ({method})')
print('All 3 mutants killed; originals were never modified.')
