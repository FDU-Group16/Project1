#!/usr/bin/env python3
"""Exercise the real staging scripts at their Docker, SSH, and Git boundaries."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40
API = "ghcr.io/example/campus-api@sha256:" + "1" * 64
WEB = "ghcr.io/example/campus-web@sha256:" + "2" * 64
POSTGRES = "ghcr.io/example/campus-postgres@sha256:" + "3" * 64
TOKEN = "fixture-token-must-stay-on-stdin"


FAKE_SYSTEM = r'''import fcntl
import json
import os
from pathlib import Path
import sys

state_file = Path(os.environ["FAKE_STATE"])
with state_file.open() as handle:
    fcntl.flock(handle, fcntl.LOCK_SH)
    state = json.load(handle)
program = Path(sys.argv[0]).name
args = sys.argv[1:]
entry = {"program": program, "args": args}
if program == "docker":
    entry["config"] = os.environ.get("DOCKER_CONFIG", "")

def finish(code=0, output=""):
    with state_file.open("r+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        current = json.load(handle)
        current["calls"].append(entry)
        if program == "docker":
            current["local"] = state["local"]
            current["registry"] = state["registry"]
        handle.seek(0)
        json.dump(current, handle)
        handle.truncate()
    if output:
        print(output)
    sys.exit(code)

if program == "docker":
    if args[:3] == ["buildx", "imagetools", "inspect"]:
        digest = state["registry"].get(args[3])
        finish(0 if digest else 1, digest or "")
    if args[:1] == ["login"]:
        received = sys.stdin.read().rstrip("\n")
        entry["token_via_stdin"] = received == os.environ["FAKE_TOKEN"]
        config = Path(entry["config"])
        if not entry["config"] or not config.is_dir():
            finish(97, "login requires a private Docker config directory")
        (config / "config.json").write_text('{"auths":{"ghcr.io":{}}}')
        finish(1 if state.get("login_failure") else 0, "Login Succeeded")
    if args[:2] == ["image", "inspect"]:
        finish(0 if args[2] in state["local"] else 1)
    if args[:1] == ["pull"]:
        ref = args[-1]
        if ref == state.get("fail_pull"):
            finish(1, "fixture registry unavailable")
        if ref not in state["local"]:
            state["local"].append(ref)
        finish()
    if args[:1] == ["tag"]:
        if args[1] not in state["local"]:
            finish(98, "attempted to tag an unavailable image")
        state["local"].append(args[2])
        finish()
    if args[:1] == ["push"]:
        state["registry"][args[1]] = state["published_digest"]
        finish()
    if args[:1] in (["info"], ["compose"]):
        finish()
    finish(99, "unexpected Docker operation: " + repr(args))

if program == "git":
    if args == ["rev-parse", "HEAD"]:
        finish(output=state["head"])
    if args[:2] == ["cat-file", "-e"]:
        finish(0 if state.get("current_known") else 1)
    if args[:2] == ["merge-base", "--is-ancestor"]:
        finish(0 if state.get("is_ancestor") else 1)
    if args[:1] == ["archive"]:
        finish(output="fixture-release-archive")
    finish(99, "unexpected Git operation: " + repr(args))

if program == "ssh":
    command = args[-1]
    if "readlink" in command:
        finish(output=state.get("current_sha", ""))
    if "--check" in command:
        finish(0 if state.get("healthy") else 1)
    if "pull-staging-images.sh" in command:
        entry["token_via_stdin"] = sys.stdin.read().rstrip("\n") == os.environ["FAKE_TOKEN"]
        finish(1 if state.get("remote_pull_failure") else 0)
    if "tar -xf" in command:
        entry["archive_received"] = "fixture-release-archive" in sys.stdin.read()
    if "images.env" in command:
        entry["images_env"] = sys.stdin.read()
    finish()

finish(99, "unexpected fake executable")
'''


class StagingImagesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="staging-images-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.bin = self.root / "bin"
        self.home = self.root / "home"
        self.tmp = self.root / "tmp"
        for directory in (self.repo / "scripts", self.repo / "docker", self.bin,
                          self.home / ".ssh", self.tmp):
            directory.mkdir(parents=True)
        for name in ("publish-staging-postgres.sh", "pull-staging-images.sh",
                     "deploy-staging-upload.sh"):
            source = ROOT / "scripts" / name
            if source.exists():
                shutil.copyfile(source, self.repo / "scripts" / name)
        source = ROOT / "docker" / "staging-postgres-image.txt"
        if source.exists():
            shutil.copyfile(source, self.repo / "docker" / source.name)
        for name in (".env.example", "compose.staging.yaml"):
            shutil.copyfile(ROOT / name, self.repo / name)
        for name in ("staging_key", "known_hosts"):
            (self.home / ".ssh" / name).write_text("fixture\n")
        for name in ("docker", "git", "ssh"):
            executable = self.bin / name
            executable.write_text(f"#!{sys.executable}\n" + FAKE_SYSTEM)
            executable.chmod(0o755)
        self.state_file = self.root / "state.json"
        self.output = self.root / "github-output"
        self.state = {
            "calls": [], "registry": {}, "local": [], "head": SHA,
            "published_digest": "sha256:" + "3" * 64,
        }
        self.save_state()
        self.env = os.environ | {
            "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
            "HOME": str(self.home), "TMPDIR": str(self.tmp),
            "FAKE_STATE": str(self.state_file), "FAKE_TOKEN": TOKEN,
            "GITHUB_SHA": SHA, "GITHUB_OUTPUT": str(self.output),
            "STAGING_IMAGE_PREFIX": "ghcr.io/example/campus",
            "STAGING_SSH_HOST": "staging.example.test", "STAGING_SSH_USER": "deploy",
            "STAGING_REGISTRY_USER": "fixture-user", "STAGING_REGISTRY_TOKEN": TOKEN,
            "STAGING_API_IMAGE": API, "STAGING_WEB_IMAGE": WEB,
            "STAGING_POSTGRES_IMAGE": POSTGRES,
        }
        self.env.pop("DOCKER_CONFIG", None)

    def save_state(self) -> None:
        self.state_file.write_text(json.dumps(self.state))

    def read_state(self) -> dict:
        self.state = json.loads(self.state_file.read_text())
        return self.state

    def run_script(self, name: str, *args: str, stdin: str = "") -> subprocess.CompletedProcess:
        result = subprocess.run(
            ["bash", str(self.repo / "scripts" / name), *args], cwd=self.repo,
            env=self.env, input=stdin, capture_output=True, text=True, timeout=20,
        )
        self.read_state()
        self.assertNotIn(TOKEN, result.stdout + result.stderr)
        self.assertNotIn(TOKEN, json.dumps(self.state["calls"]))
        return result

    def docker_calls(self, *prefix: str) -> list[dict]:
        return [call for call in self.state["calls"] if call["program"] == "docker"
                and call["args"][:len(prefix)] == list(prefix)]

    def assert_success(self, result: subprocess.CompletedProcess) -> None:
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def assert_auth_cleaned(self) -> None:
        logins = self.docker_calls("login")
        self.assertEqual(len(logins), 1)
        self.assertTrue(logins[0]["token_via_stdin"])
        configs = {call["config"] for call in self.docker_calls() if call["config"]}
        self.assertEqual(len(configs), 1)
        config = Path(configs.pop())
        self.assertTrue(str(config).startswith(str(self.tmp) + os.sep))
        self.assertFalse(config.exists(), "temporary Docker credentials survived the script")
        self.assertEqual(list(self.tmp.iterdir()), [])

    def pull_images(self) -> subprocess.CompletedProcess:
        return self.run_script("pull-staging-images.sh", SHA, "fixture-user", API, WEB,
                               POSTGRES, stdin=TOKEN + "\n")

    def test_postgres_second_publish_reuses_registry_image(self) -> None:
        self.assert_success(self.run_script("publish-staging-postgres.sh"))
        self.assertEqual(len(self.docker_calls("pull")), 1)
        self.assertEqual(self.docker_calls("pull")[0]["args"][1:3],
                         ["--platform", "linux/amd64"])
        self.assertEqual(len(self.docker_calls("push")), 1)
        first_output = self.output.read_text()
        self.assertIn("image=" + POSTGRES + "\n", first_output)
        self.assert_success(self.run_script("publish-staging-postgres.sh"))
        self.assertEqual(len(self.docker_calls("pull")), 1)
        self.assertEqual(len(self.docker_calls("tag")), 1)
        self.assertEqual(len(self.docker_calls("push")), 1)

    def test_existing_local_digests_are_reused(self) -> None:
        self.state["local"] = [API, WEB, POSTGRES]
        self.save_state()
        self.assert_success(self.pull_images())
        self.assertEqual(self.docker_calls("pull"), [])
        aliases = {call["args"][2]: call["args"][1] for call in self.docker_calls("tag")}
        expected = {f"campus-resource-{service}:{SHA}": API
                    for service in ("m1", "m2", "m3", "d")}
        expected |= {f"campus-resource-web:{SHA}": WEB,
                     f"campus-resource-postgres:{SHA}": POSTGRES}
        self.assertEqual(aliases, expected)
        self.assertEqual(self.docker_calls("login"), [])
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_only_missing_local_digest_is_pulled(self) -> None:
        self.state["local"] = [API, POSTGRES]
        self.save_state()
        self.assert_success(self.pull_images())
        self.assertEqual([call["args"] for call in self.docker_calls("pull")],
                         [["pull", "--platform", "linux/amd64", WEB]])
        self.assertEqual(len(self.docker_calls("tag")), 6)
        self.assert_auth_cleaned()

    def test_failed_third_pull_does_not_tag_any_release_alias(self) -> None:
        self.state["fail_pull"] = POSTGRES
        self.save_state()
        result = self.pull_images()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual([call["args"][-1] for call in self.docker_calls("pull")],
                         [API, WEB, POSTGRES])
        self.assertEqual(self.docker_calls("tag"), [])
        self.assert_auth_cleaned()

    def test_failed_login_removes_temporary_credentials(self) -> None:
        self.state["login_failure"] = True
        self.save_state()
        self.assertNotEqual(self.pull_images().returncode, 0)
        self.assertEqual(self.docker_calls("pull"), [])
        self.assertEqual(self.docker_calls("tag"), [])
        self.assert_auth_cleaned()

    def test_mutable_image_tag_is_rejected_before_login(self) -> None:
        result = self.run_script("pull-staging-images.sh", SHA, "fixture-user", API,
                                 "ghcr.io/example/campus-web:latest", POSTGRES,
                                 stdin=TOKEN + "\n")
        self.assertNotEqual(result.returncode, 0)
        for operation in ("login", "pull", "tag"):
            self.assertEqual(self.docker_calls(operation), [])

    def test_upload_healthy_newer_release_skips_publication(self) -> None:
        self.state |= {"current_sha": "b" * 40, "current_known": True,
                       "is_ancestor": True, "healthy": True}
        self.save_state()
        self.assert_success(self.run_script("deploy-staging-upload.sh"))
        ssh_commands = [call["args"][-1] for call in self.state["calls"]
                        if call["program"] == "ssh"]
        self.assertEqual(len(ssh_commands), 2)
        self.assertIn("--check", ssh_commands[1])
        self.assertFalse(any(call["program"] == "git" and call["args"][0] == "archive"
                             for call in self.state["calls"]))
        self.assertEqual([call["args"][0] for call in self.docker_calls()], ["compose"])

    def test_upload_passes_only_sources_and_digests_before_activation(self) -> None:
        self.assert_success(self.run_script("deploy-staging-upload.sh"))
        self.assertEqual([call["args"][0] for call in self.docker_calls()], ["compose"])
        ssh_calls = [call for call in self.state["calls"] if call["program"] == "ssh"]
        archive_calls = [call for call in ssh_calls if "tar -xf" in call["args"][-1]]
        self.assertEqual(len(archive_calls), 1)
        self.assertTrue(archive_calls[0]["archive_received"])
        image_records = [call["images_env"] for call in ssh_calls if "images_env" in call]
        self.assertEqual(image_records,
                         [f"API_IMAGE={API}\nWEB_IMAGE={WEB}\nPOSTGRES_IMAGE={POSTGRES}\n"])
        pulls = [call for call in ssh_calls if "pull-staging-images.sh" in call["args"][-1]]
        self.assertEqual(len(pulls), 1)
        self.assertTrue(pulls[0]["token_via_stdin"])
        self.assertIn("activate-staging.sh", ssh_calls[-1]["args"][-1])
        self.assertLess(ssh_calls.index(pulls[0]), len(ssh_calls) - 1)

    def test_upload_failed_remote_pull_does_not_activate(self) -> None:
        self.state["remote_pull_failure"] = True
        self.save_state()
        self.assertNotEqual(self.run_script("deploy-staging-upload.sh").returncode, 0)
        commands = [call["args"][-1] for call in self.state["calls"]
                    if call["program"] == "ssh"]
        self.assertTrue(any("pull-staging-images.sh" in command for command in commands))
        self.assertFalse(any("activate-staging.sh" in command for command in commands))


if __name__ == "__main__":
    unittest.main(verbosity=2)
