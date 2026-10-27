"""Run three bounded mutations in disposable source copies, never the checkout.

Usage: .venv/bin/python services/m3/tests/mutation_check.py
Requires the same local-loopback permission as test_independent.py. Every target
must pass unmodified first; a mutation is killed only by its assertion failure.
Database environment overrides are removed: all cases use temporary SQLite.
"""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


@dataclass(frozen=True)
class Mutation:
    name: str
    path: str
    old: str
    new: str
    test: str


TEST_FILE = "services/m3/tests/test_independent.py"
MUTATIONS = (
    Mutation(
        "object-authorization",
        "services/m3/service.py",
        'return (actor.can("dispatch") or order["reporterId"] == actor.id\n'
        '                or actor.can("work") and order["assigneeId"] == actor.id)',
        'return True  # MUTATION: disclose every work order',
        "test_object_authorization_idempotency_and_stale_version",
    ),
    Mutation(
        "premature-repair-state",
        "services/m3/service.py",
        'order["status"], order["_blockStartsAt"] = "BLOCK_PENDING", iso(now)',
        'order["status"], order["_blockStartsAt"] = "IN_PROGRESS", iso(now)',
        "test_reassignment_revokes_previous_worker_without_extending_sla",
    ),
    Mutation(
        "receipt-validation-bypass",
        "services/m3/m1_client.py",
        "return validate_receipt(receipt, source_id, payload)",
        "return receipt  # MUTATION: trust an unvalidated network response",
        "test_invalid_http_receipt_cannot_advance_work_order[wrong-system]",
    ),
)


def run_pytest(root, tests):
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith("M3_") and key != "PYTHONPATH"}
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=short", "-p", "no:cacheprovider", *tests],
        cwd=root, env=environment, text=True, capture_output=True, timeout=90,
    )


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    repository = Path(__file__).resolve().parents[3]
    originals = {mutation.path: digest(repository / mutation.path) for mutation in MUTATIONS}
    with tempfile.TemporaryDirectory(prefix="m3-mutation-") as temporary:
        sandbox = Path(temporary)
        baseline = sandbox / "baseline"
        (baseline / "services").mkdir(parents=True)
        shutil.copy2(repository / "services/__init__.py", baseline / "services/__init__.py")
        shutil.copytree(
            repository / "services/m3", baseline / "services/m3",
            ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.db", "*.db-*", "*.sqlite*", ".data"),
        )
        tests = [f"{TEST_FILE}::{mutation.test}" for mutation in MUTATIONS]
        clean = run_pytest(baseline, tests)
        print("BASELINE", clean.stdout.strip(), flush=True)
        if clean.returncode != 0:
            print(clean.stderr, file=sys.stderr)
            raise SystemExit("Unmodified target tests failed; no mutation result is valid.")

        for mutation in MUTATIONS:
            mutated = sandbox / mutation.name
            shutil.copytree(baseline, mutated)
            source_path = mutated / mutation.path
            source = source_path.read_text()
            if source.count(mutation.old) != 1:
                raise SystemExit(f"{mutation.name}: mutation anchor must occur exactly once; update the check.")
            source_path.write_text(source.replace(mutation.old, mutation.new, 1))
            result = run_pytest(mutated, [f"{TEST_FILE}::{mutation.test}"])
            assertion_failure = re.search(r"^E\s+(?:AssertionError|assert\b)", result.stdout, re.MULTILINE)
            if result.returncode != 1 or "1 failed" not in result.stdout or not assertion_failure:
                print(result.stdout, result.stderr, file=sys.stderr)
                raise SystemExit(f"{mutation.name}: survived or failed for a non-assertion reason.")
            print(f"KILLED {mutation.name}: {mutation.test}", flush=True)

    if any(digest(repository / path) != expected for path, expected in originals.items()):
        raise SystemExit("Source changed during mutation verification; inspect concurrent edits and rerun.")
    print("PASS: 3 baseline tests passed; 3/3 targeted mutations killed; checkout source unchanged.")


if __name__ == "__main__":
    main()
