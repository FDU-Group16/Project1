"""Exercise the dependency handoff CLI against isolated repository fixtures.

These tests execute the real checker and inspect its exit status and report.
Fixture revisions and reports are synthetic; they do not establish provider
availability or integration evidence for this repository.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CHECKER = Path(__file__).resolve().with_name("check-dependencies.py")
PROVIDER_REVISION = "1" * 40
UPDATED_PROVIDER_REVISION = "2" * 40
CONSUMER_REVISION = "3" * 40
DEPENDENCY_ID = "M1-D-IDENTITY"
MARKER_PATH = "services/m1/temporary.py"


class DependencyHandoffCLI(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="dependency-handoff-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for name in (
            "services/d/STATUS.md",
            "services/m1/STATUS.md",
            "services/m1/inventory.md",
            "services/d/evidence.md",
            "services/m1/evidence.md",
            "contracts/identity.md",
        ):
            self.write(name, "# Synthetic fixture only\n")
        self.write(MARKER_PATH, f"# TEMPORARY-DEPENDENCY {DEPENDENCY_ID}: fixture\n")
        self.capability = {
            "id": "D-01",
            "owner": "M2",
            "status": "not_ready",
            "status_file": "services/d/STATUS.md",
            "contract": self.contract(),
            "implementation": None,
        }
        self.providers = {"schema_version": 1, "capabilities": [self.capability]}
        self.dependency = {
            "id": DEPENDENCY_ID,
            "providers": ["D-01"],
            "status": "temporary",
            "inventory": "services/m1/inventory.md",
            "contract": self.contract(),
            "marker_paths": [MARKER_PATH],
            "verification": None,
        }
        self.consumer = {
            "schema_version": 1,
            "consumer": "M1",
            "owner": "M1",
            "status_file": "services/m1/STATUS.md",
            "dependencies": [self.dependency],
        }

    @staticmethod
    def contract():
        return {"path": "contracts/identity.md", "version": "0.1.0", "status": "proposed"}

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def write_json(self, name, content):
        self.write(name, json.dumps(content, ensure_ascii=False, indent=2) + "\n")

    def ready(self, capability=None, revision=PROVIDER_REVISION):
        capability = self.capability if capability is None else capability
        capability["status"] = "integration_ready"
        capability["implementation"] = {
            "revision": revision,
            "evidence": "services/d/evidence.md",
        }

    def verified(self, status="verified"):
        self.dependency["status"] = status
        self.dependency["verification"] = {
            "consumer_revision": CONSUMER_REVISION,
            "provider_revisions": {
                item["id"]: item["implementation"]["revision"]
                for item in self.providers["capabilities"]
                if item["id"] in self.dependency["providers"]
            },
            "environment": "isolated synthetic CLI fixture",
            "command": "python3 fixture-integration-check.py",
            "evidence": "services/m1/evidence.md",
        }

    def run_checker(self, *arguments, expected=0):
        self.write_json("services/d/PROVIDES.json", self.providers)
        self.write_json("services/m1/DEPENDENCIES.json", self.consumer)
        env = os.environ.copy()
        env.pop("GITHUB_ACTIONS", None)
        result = subprocess.run(
            [sys.executable, str(CHECKER), "--root", str(self.root), "--json", *arguments],
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        diagnostic = f"exit={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        self.assertEqual(result.returncode, expected, diagnostic)
        if expected == 2 and not result.stdout.strip():
            self.assertTrue(result.stderr.strip(), diagnostic)
            return None
        try:
            report = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"CLI did not return a JSON report: {diagnostic}\n{exc}")
        self.assertIsInstance(report, dict, diagnostic)
        for field in ("providers", "dependencies", "errors", "warnings"):
            self.assertIsInstance(report.get(field), list, diagnostic)
        if expected == 0:
            self.assertEqual(report["errors"], [], diagnostic)
        return report

    def selected(self, report):
        self.assertEqual(len(report["dependencies"]), 1, report)
        return report["dependencies"][0]

    def test_unavailable_provider_is_a_visible_pending_dependency(self):
        item = self.selected(self.run_checker("--provider", "D-01"))
        self.assertEqual(item["id"], DEPENDENCY_ID)
        self.assertEqual(item["consumer"], "M1")
        self.assertEqual(item["status"], "temporary")
        self.assertEqual(item["action"], "wait_provider")
        self.assertFalse(item["complete"])
        self.assertEqual(item["providers"][0]["owner"], "M2")
        self.assertEqual(item["inventory"], "services/m1/inventory.md")

    def test_ready_provider_exposes_pending_consumer_without_blocking_default_ci(self):
        self.ready()
        report = self.run_checker("--provider-owner", "M2")
        item = self.selected(report)
        self.assertEqual(item["action"], "integrate")
        self.assertFalse(item["complete"])
        self.assertTrue(report["warnings"], report)
        strict = self.run_checker("--provider", "D-01", "--require-complete", expected=1)
        self.assertFalse(self.selected(strict)["complete"])

    def test_verified_consumer_still_needs_cleanup(self):
        self.ready()
        self.verified()
        report = self.run_checker()
        self.assertEqual(self.selected(report)["action"], "cleanup")
        self.run_checker("--consumer", "M1", "--require-complete", expected=1)

    def test_cleaned_retains_real_client_assumption_and_deleted_path_history(self):
        self.ready()
        self.verified("cleaned")
        (self.root / MARKER_PATH).unlink()
        self.write("services/m1/client.py", f"# CONTRACT-ASSUMPTION {DEPENDENCY_ID}: retain client\n")
        report = self.run_checker("--provider", "D-01", "--consumer", "M1", "--require-complete")
        item = self.selected(report)
        self.assertEqual(item["action"], "complete")
        self.assertTrue(item["complete"])
        self.assertEqual(item["verification"]["provider_revisions"]["D-01"], PROVIDER_REVISION)

    def test_cleaned_with_remaining_temporary_marker_is_rejected(self):
        self.ready()
        self.verified("cleaned")
        report = self.run_checker(expected=1)
        self.assertTrue(report["errors"], report)
        self.assertIn(DEPENDENCY_ID, "\n".join(report["errors"]))

    def test_verified_requires_complete_real_integration_evidence(self):
        self.ready()
        self.verified()
        evidence = copy.deepcopy(self.dependency["verification"])
        invalid = [None]
        for field in ("consumer_revision", "provider_revisions", "environment", "command", "evidence"):
            value = copy.deepcopy(evidence)
            del value[field]
            invalid.append(value)
        invalid.append({**evidence, "evidence": "services/m1/missing-report.md"})
        invalid.append({**evidence, "provider_revisions": {}})
        invalid.append({**evidence, "consumer_revision": "not-a-revision"})
        for value in invalid:
            with self.subTest(verification=value):
                self.dependency["verification"] = value
                self.assertTrue(self.run_checker(expected=1)["errors"])

    def test_ready_provider_requires_implementation_revision_and_existing_report(self):
        self.ready()
        implementation = copy.deepcopy(self.capability["implementation"])
        invalid = [
            None,
            {"revision": PROVIDER_REVISION},
            {"evidence": "services/d/evidence.md"},
            {**implementation, "revision": "not-a-revision"},
            {**implementation, "evidence": "services/d/missing-report.md"},
        ]
        for value in invalid:
            with self.subTest(implementation=value):
                self.capability["implementation"] = value
                self.assertTrue(self.run_checker(expected=1)["errors"])

    def test_new_unregistered_marker_and_undeclared_paths_are_rejected(self):
        extra = "services/m1/extra.py"
        self.write(extra, "# TEMPORARY-DEPENDENCY UNREGISTERED-IDENTITY: fixture\n")
        self.assertTrue(self.run_checker(expected=1)["errors"])
        self.write(extra, f"# TEMPORARY-DEPENDENCY {DEPENDENCY_ID}: undeclared source\n")
        self.assertTrue(self.run_checker(expected=1)["errors"])
        (self.root / extra).unlink()
        self.dependency["marker_paths"] = []
        self.assertTrue(self.run_checker(expected=1)["errors"])

    def test_registered_path_without_marker_is_rejected(self):
        self.write(MARKER_PATH, "# Temporary implementation accidentally lost its marker.\n")
        self.assertTrue(self.run_checker(expected=1)["errors"])

    def test_duplicate_ids_unknown_provider_and_invalid_enums_are_rejected(self):
        with self.subTest(problem="duplicate dependency"):
            self.consumer["dependencies"].append(copy.deepcopy(self.dependency))
            self.assertTrue(self.run_checker(expected=1)["errors"])
            self.consumer["dependencies"].pop()
        with self.subTest(problem="duplicate provider"):
            self.providers["capabilities"].append(copy.deepcopy(self.capability))
            self.assertTrue(self.run_checker(expected=1)["errors"])
            self.providers["capabilities"].pop()
        with self.subTest(problem="unknown provider"):
            self.dependency["providers"] = ["D-99"]
            self.assertTrue(self.run_checker(expected=1)["errors"])
            self.dependency["providers"] = ["D-01"]
        with self.subTest(problem="invalid state"):
            self.dependency["status"] = "done"
            self.assertTrue(self.run_checker(expected=1)["errors"])
            self.dependency["status"] = "temporary"
        with self.subTest(problem="invalid contract state"):
            self.dependency["contract"]["status"] = "accepted"
            self.assertTrue(self.run_checker(expected=1)["errors"])

    def test_multiple_providers_and_shared_marker_file_are_discovered(self):
        second_provider = copy.deepcopy(self.capability)
        second_provider.update(id="D-03", owner="M3")
        self.providers["capabilities"].append(second_provider)
        self.dependency["providers"] = ["D-01", "D-03"]
        web_id = "WEB-D01-IDENTITY"
        self.write("apps/web/STATUS.md", "# Synthetic Web fixture\n")
        self.write("apps/web/src/shared/auth/inventory.md", "# Synthetic inventory\n")
        web_dependency = copy.deepcopy(self.dependency)
        web_dependency.update(id=web_id, providers=["D-01"], inventory="apps/web/src/shared/auth/inventory.md")
        self.write_json("apps/web/src/shared/auth/DEPENDENCIES.json", {
            "schema_version": 1,
            "consumer": "WEB-M1-D02",
            "owner": "Web/M1",
            "status_file": "apps/web/STATUS.md",
            "dependencies": [web_dependency],
        })
        self.write(MARKER_PATH, f"# TEMPORARY-DEPENDENCY {DEPENDENCY_ID} / {web_id}：shared entry\n")
        self.ready()
        report = self.run_checker("--provider", "D-01")
        self.assertEqual({item["id"] for item in report["dependencies"]}, {DEPENDENCY_ID, web_id})
        actions = {item["id"]: item["action"] for item in report["dependencies"]}
        self.assertEqual(actions[DEPENDENCY_ID], "wait_provider")
        self.assertEqual(actions[web_id], "integrate")
        self.ready(second_provider)
        report = self.run_checker("--provider-owner", "M3")
        self.assertEqual(self.selected(report)["action"], "integrate")
        self.run_checker("--provider", "D-03", "--provider-owner", "M2", expected=2)
        report = self.run_checker("--provider", "D-03", "--provider-owner", "M3", "--consumer", "M1")
        self.assertEqual(self.selected(report)["action"], "integrate")

    def test_comma_markers_include_every_dependency_and_reject_trailing_separators(self):
        second_id = "M1-D-NOTIFICATIONS"
        second = copy.deepcopy(self.dependency)
        second["id"] = second_id
        self.consumer["dependencies"].append(second)
        self.write(MARKER_PATH, f"# TEMPORARY-DEPENDENCY {DEPENDENCY_ID}, {second_id}: shared fixture\n")
        report = self.run_checker()
        self.assertEqual({item["id"] for item in report["dependencies"]}, {DEPENDENCY_ID, second_id})
        self.consumer["dependencies"].pop()
        report = self.run_checker(expected=1)
        self.assertIn(second_id, "\n".join(report["errors"]))
        for separator in ("/", ","):
            with self.subTest(separator=separator):
                self.write(MARKER_PATH, f"# TEMPORARY-DEPENDENCY {DEPENDENCY_ID} {separator}: malformed fixture\n")
                report = self.run_checker(expected=1)
                self.assertTrue(any("malformed" in error for error in report["errors"]), report)

    def test_invalid_manifest_shapes_are_reported_even_outside_selected_consumer(self):
        extra_path = "services/m2/PROVIDES.json"
        invalid = [
            None,
            [],
            "not an object",
            {"schema_version": True, "capabilities": []},
            {"schema_version": "1", "capabilities": []},
            {"schema_version": 1, "capabilities": None},
            {"schema_version": 1, "capabilities": {}},
            {"schema_version": 1, "capabilities": [None]},
            {"schema_version": 1, "capabilities": [[]]},
        ]
        for value in invalid:
            with self.subTest(manifest=value):
                self.write_json(extra_path, value)
                report = self.run_checker("--consumer", "M1", expected=1)
                self.assertTrue(report["errors"], report)
                self.assertEqual(self.selected(report)["id"], DEPENDENCY_ID)
        for content in (
            "{not valid JSON}",
            '{"schema_version":1,"capabilities":[],"capabilities":[]}',
        ):
            with self.subTest(content=content):
                self.write(extra_path, content)
                self.assertTrue(self.run_checker("--consumer", "M1", expected=1)["errors"])

    def test_invalid_nested_types_produce_json_errors(self):
        invalid = [
            ("id", []),
            ("providers", "D-01"),
            ("providers", []),
            ("providers", [None]),
            ("providers", [["D-01"]]),
            ("status", {}),
            ("inventory", []),
            ("contract", []),
            ("marker_paths", MARKER_PATH),
            ("marker_paths", [{}]),
            ("verification", []),
        ]
        for field, value in invalid:
            original = copy.deepcopy(self.dependency[field])
            with self.subTest(field=field, value=value):
                self.dependency[field] = value
                self.assertTrue(self.run_checker(expected=1)["errors"])
            self.dependency[field] = original

    def test_empty_consumer_and_provider_manifests_cannot_satisfy_strict_selection(self):
        empty_consumer = copy.deepcopy(self.consumer)
        empty_consumer.update(consumer="M2", owner="M2", dependencies=[])
        self.write_json("apps/web/src/modules/m2/DEPENDENCIES.json", empty_consumer)
        self.write_json("services/m2/PROVIDES.json", {"schema_version": 1, "capabilities": []})
        self.assertEqual(self.selected(self.run_checker())["consumer"], "M1")
        self.run_checker("--consumer", "M2", "--require-complete", expected=2)
        self.run_checker("--provider-owner", "M9", "--require-complete", expected=2)

    def test_strict_scope_allows_unselected_pending_dependencies(self):
        self.ready()
        self.verified("cleaned")
        (self.root / MARKER_PATH).unlink()
        other = copy.deepcopy(self.dependency)
        other.update(id="WEB-D01-IDENTITY", status="temporary", marker_paths=[], verification=None)
        self.write_json("apps/web/src/modules/m1/DEPENDENCIES.json", {
            "schema_version": 1,
            "consumer": "WEB-M1",
            "owner": "M1",
            "status_file": "services/m1/STATUS.md",
            "dependencies": [other],
        })
        report = self.run_checker("--consumer", "M1", "--require-complete")
        self.assertTrue(self.selected(report)["complete"])
        self.run_checker("--provider", "D-01", "--require-complete", expected=1)

    def test_filter_does_not_hide_invalid_marker_elsewhere(self):
        self.write("services/m3/unregistered.py", "# TEMPORARY-DEPENDENCY OTHER-UNKNOWN: fixture\n")
        report = self.run_checker("--provider", "D-01", expected=1)
        self.assertTrue(report["errors"], report)
        self.assertIn("OTHER-UNKNOWN", "\n".join(report["errors"]))

    def test_unknown_empty_and_unscoped_strict_filters_do_not_pass(self):
        for arguments in (
            ("--require-complete",),
            ("--provider", "D-99"),
            ("--provider-owner", "M9"),
            ("--consumer", "unknown"),
            ("--provider", "D-01", "--consumer", "unknown", "--require-complete"),
        ):
            with self.subTest(arguments=arguments):
                self.run_checker(*arguments, expected=2)

    def test_registered_provider_with_no_consumers_is_not_empty_strict_success(self):
        unused = copy.deepcopy(self.capability)
        unused["id"] = "D-99"
        self.providers["capabilities"].append(unused)
        self.run_checker("--provider", "D-99", "--require-complete", expected=2)

    def test_provider_revision_change_requires_reverification_without_erasing_history(self):
        self.ready()
        self.verified("cleaned")
        (self.root / MARKER_PATH).unlink()
        self.capability["implementation"]["revision"] = UPDATED_PROVIDER_REVISION
        report = self.run_checker()
        item = self.selected(report)
        self.assertEqual(item["status"], "cleaned")
        self.assertEqual(item["action"], "reverify")
        self.assertFalse(item["complete"])
        self.assertEqual(item["verification"]["provider_revisions"]["D-01"], PROVIDER_REVISION)
        self.assertTrue(report["warnings"], report)
        self.run_checker("--provider", "D-01", "--require-complete", expected=1)

    def test_relative_path_escape_is_rejected(self):
        original = self.dependency["inventory"]
        for value in ("../outside.md", str(self.root / original)):
            with self.subTest(path=value):
                self.dependency["inventory"] = value
                self.assertTrue(self.run_checker(expected=1)["errors"])

    def test_symlinked_evidence_outside_root_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="dependency-outside-test-") as directory:
            outside = Path(directory) / "report.md"
            outside.write_text("Synthetic outside-root fixture", encoding="utf-8")
            link = self.root / "services/m1/outside-report.md"
            link.symlink_to(outside)
            self.dependency["inventory"] = "services/m1/outside-report.md"
            self.assertTrue(self.run_checker(expected=1)["errors"])

    def test_documentation_private_env_and_worktree_copies_are_not_scanned(self):
        marker = "# TEMPORARY-DEPENDENCY IGNORED-IDENTITY: not source\n"
        for name in (
            "services/m1/history.md",
            "services/m1/.env",
            "apps/web/.env",
            ".worktrees/copy/services/m1/temporary.py",
            "services/m1/.worktrees/copy/temporary.py",
            "services/m1/.venv/fixture.py",
            "apps/web/src/node_modules/fixture.js",
        ):
            self.write(name, marker)
        self.assertEqual(self.selected(self.run_checker())["id"], DEPENDENCY_ID)

    def test_web_env_example_is_scanned(self):
        self.write("apps/web/.env.example", "# TEMPORARY-DEPENDENCY WEB-UNKNOWN: opt-in only\n")
        self.assertTrue(self.run_checker(expected=1)["errors"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
