#!/usr/bin/env python3
"""Read dependency inventories and source markers without changing their state.

Evidence paths and revisions are declarations, not proof that integration ran.
This checker validates their consistency without reading evidence or credentials.
"""

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys


ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]*\Z")
REVISION = re.compile(r"[0-9a-fA-F]{40}\Z")
MARKER = re.compile(r"\b(TEMPORARY-DEPENDENCY|CONTRACT-ASSUMPTION)\b")
MARKER_IDS = re.compile(r"\s+([A-Za-z][A-Za-z0-9_-]*(?:[ \t]*[/,][ \t]*[A-Za-z][A-Za-z0-9_-]*)*)")
IGNORED = {".git", ".worktrees", "node_modules", ".venv", "venv", "__pycache__",
           ".pytest_cache", ".mypy_cache", ".ruff_cache", ".uv-cache", "dist", "coverage"}
MANIFESTS = (
    "services/*/PROVIDES.json", "services/*/DEPENDENCIES.json",
    "apps/web/src/modules/*/DEPENDENCIES.json",
    "apps/web/src/shared/*/DEPENDENCIES.json",
)


class Invalid(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Invalid(message)


def string(value, label):
    require(isinstance(value, str) and bool(value.strip()), label + " must be a non-empty string")
    return value


def identifier(value, label):
    string(value, label)
    require(ID.fullmatch(value) is not None, label + " has an invalid ID")
    return value


def revision(value, label):
    require(isinstance(value, str) and REVISION.fullmatch(value) is not None,
            label + " must be a 40-character hexadecimal revision")


def fields(value, names, label):
    require(isinstance(value, dict), label + " must be an object")
    missing = set(names) - set(value)
    extra = set(value) - set(names)
    require(not missing, label + " missing fields: " + ", ".join(sorted(missing)))
    require(not extra, label + " unknown fields: " + ", ".join(sorted(extra)))


def unique_strings(value, label, nonempty=False):
    require(isinstance(value, list), label + " must be an array")
    if nonempty:
        require(bool(value), label + " must not be empty")
    for item in value:
        string(item, label + " item")
    require(len(set(value)) == len(value), label + " contains duplicates")


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Invalid("duplicate JSON key: " + key)
        result[key] = value
    return result


def source_path(relative):
    parts = PurePosixPath(relative).parts
    if any(part in IGNORED for part in parts):
        return False
    if relative == "apps/web/.env.example":
        return True
    if PurePosixPath(relative).name.startswith(".env"):
        return False
    return ((relative.startswith("services/") or relative.startswith("apps/web/src/"))
            and PurePosixPath(relative).suffix in {".py", ".ts", ".vue", ".js"})


class Audit:
    def __init__(self, root):
        self.providers = {}
        self.dependencies = {}
        self.consumers = set()
        self.errors = []
        self.temporary = {}
        self.root = root.absolute()
        try:
            self.root = root.resolve()
        except (OSError, RuntimeError, ValueError):
            self.errors.append("repository root cannot be resolved safely")

    def path(self, value, label, exists=True):
        string(value, label)
        path = PurePosixPath(value)
        require(not path.is_absolute() and ".." not in path.parts and "\\" not in value
                and ":" not in value and str(path) == value and value != "."
                and not any(ord(character) < 32 for character in value),
                label + " must be a normalized repository-relative path")
        require(not any(part in IGNORED for part in path.parts), label + " uses an excluded directory")
        target = self.root.joinpath(*path.parts)
        try:
            resolved = target.resolve()
        except (OSError, RuntimeError):
            raise Invalid(label + " cannot be resolved safely")
        require(resolved.is_relative_to(self.root), label + " escapes repository root")
        require(not (resolved.name.startswith(".env") and resolved.name != ".env.example"),
                label + " must not reference a real environment/credential file")
        if exists:
            require(target.is_file(), label + " file does not exist: " + value)
        return target

    def contract(self, value, label):
        fields(value, {"path", "version", "status"}, label)
        self.path(value["path"], label + ".path")
        string(value["version"], label + ".version")
        require(value["status"] in ("proposed", "approved"), label + ".status must be proposed or approved")

    def capability(self, value, label):
        fields(value, {"id", "owner", "status", "status_file", "contract", "implementation"}, label)
        identifier(value["id"], label + ".id")
        string(value["owner"], label + ".owner")
        require(value["status"] in ("not_ready", "integration_ready"), label + ".status is invalid")
        self.path(value["status_file"], label + ".status_file")
        self.contract(value["contract"], label + ".contract")
        implementation = value["implementation"]
        if implementation is not None:
            fields(implementation, {"revision", "evidence"}, label + ".implementation")
            revision(implementation["revision"], label + ".implementation.revision")
            self.path(implementation["evidence"], label + ".implementation.evidence")
        require(value["status"] != "integration_ready" or implementation is not None,
                label + " integration_ready requires implementation revision and evidence")

    def dependency(self, value, label):
        fields(value, {"id", "providers", "status", "inventory", "contract", "marker_paths", "verification"}, label)
        identifier(value["id"], label + ".id")
        unique_strings(value["providers"], label + ".providers", nonempty=True)
        for provider in value["providers"]:
            identifier(provider, label + ".providers item")
        require(value["status"] in ("temporary", "integrating", "verified", "cleaned"), label + ".status is invalid")
        self.path(value["inventory"], label + ".inventory")
        self.contract(value["contract"], label + ".contract")
        unique_strings(value["marker_paths"], label + ".marker_paths")
        for path in value["marker_paths"]:
            self.path(path, label + ".marker_paths", exists=value["status"] != "cleaned")
            require(source_path(path), label + ".marker_paths must reference a scanned source or configuration example: " + path)
        verification = value["verification"]
        if verification is not None:
            fields(verification, {"consumer_revision", "provider_revisions", "environment", "command", "evidence"}, label + ".verification")
            revision(verification["consumer_revision"], label + ".verification.consumer_revision")
            require(isinstance(verification["provider_revisions"], dict), label + ".verification.provider_revisions must be an object")
            require(set(verification["provider_revisions"]) == set(value["providers"]),
                    label + ".verification.provider_revisions must cover exactly the declared providers")
            for provider, sha in verification["provider_revisions"].items():
                revision(sha, label + ".verification.provider_revisions." + provider)
            string(verification["environment"], label + ".verification.environment")
            string(verification["command"], label + ".verification.command")
            self.path(verification["evidence"], label + ".verification.evidence")
        require(value["status"] not in ("verified", "cleaned") or verification is not None,
                label + " verified/cleaned requires real-provider verification revisions and evidence")

    def load(self):
        for pattern in MANIFESTS:
            for manifest in sorted(self.root.glob(pattern)):
                relative = manifest.relative_to(self.root).as_posix()
                try:
                    self.path(relative, relative)
                    require(not manifest.is_symlink(), relative + " manifest must not be a symlink")
                    data = json.loads(manifest.read_text(encoding="utf-8"), object_pairs_hook=no_duplicate_keys)
                    provider_file = manifest.name == "PROVIDES.json"
                    expected = {"schema_version", "capabilities"} if provider_file else {
                        "schema_version", "consumer", "owner", "status_file", "dependencies"}
                    fields(data, expected, relative)
                    require(type(data["schema_version"]) is int and data["schema_version"] == 1,
                            relative + " schema_version must be 1")
                    key = "capabilities" if provider_file else "dependencies"
                    require(isinstance(data[key], list), relative + "." + key + " must be an array")
                    if not provider_file:
                        string(data["consumer"], relative + ".consumer")
                        string(data["owner"], relative + ".owner")
                        self.path(data["status_file"], relative + ".status_file")
                        self.consumers.add(data["consumer"])
                    for index, value in enumerate(data[key]):
                        label = "{}:{}[{}]".format(relative, key, index)
                        try:
                            if provider_file:
                                self.capability(value, label)
                                require(value["id"] not in self.providers, "duplicate capability ID: " + value["id"])
                                self.providers[value["id"]] = value
                            else:
                                self.dependency(value, label)
                                require(value["id"] not in self.dependencies, "duplicate dependency ID: " + value["id"])
                                self.dependencies[value["id"]] = dict(value, consumer=data["consumer"], owner=data["owner"])
                        except (Invalid, TypeError) as error:
                            self.errors.append(label + ": " + str(error))
                except (Invalid, OSError, ValueError, TypeError) as error:
                    self.errors.append(relative + ": " + str(error))

    def sources(self):
        for directory in (self.root / "services", self.root / "apps/web/src"):
            if directory.is_symlink() or not directory.exists():
                continue
            if not directory.resolve().is_relative_to(self.root):
                continue
            def walk_error(error):
                self.errors.append("cannot inspect source directory: " + str(error))
            for current, directories, files in os.walk(directory, followlinks=False, onerror=walk_error):
                directories[:] = sorted(name for name in directories
                                         if name not in IGNORED and not (Path(current) / name).is_symlink())
                for name in sorted(files):
                    path = Path(current) / name
                    relative = path.relative_to(self.root).as_posix()
                    if source_path(relative):
                        yield path
        example = self.root / "apps/web/.env.example"
        if example.is_file():
            yield example

    def scan(self):
        for path in self.sources():
            relative = path.relative_to(self.root).as_posix()
            try:
                # Never follow a source symlink to a file outside the scan surface.
                resolved = path.resolve()
                if not resolved.is_relative_to(self.root) or not source_path(resolved.relative_to(self.root).as_posix()):
                    continue
                for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    for marker in MARKER.finditer(line):
                        found = MARKER_IDS.match(line, marker.end())
                        location = "{}:{}".format(relative, number)
                        if not found or line[found.end():].lstrip().startswith(("/", ",")):
                            self.errors.append(location + ": malformed " + marker.group(1) + " marker")
                            continue
                        for dependency_id in re.split(r"\s*[/,]\s*", found.group(1)):
                            if dependency_id not in self.dependencies:
                                self.errors.append(location + ": unregistered dependency marker " + dependency_id)
                            if marker.group(1) == "TEMPORARY-DEPENDENCY":
                                self.temporary.setdefault(dependency_id, set()).add(relative)
            except (OSError, UnicodeError, RuntimeError) as error:
                self.errors.append(relative + ": cannot inspect source: " + str(error))
        for dependency in self.dependencies.values():
            name = dependency["id"]
            for provider in dependency["providers"]:
                if provider not in self.providers:
                    self.errors.append(name + ": unknown provider " + provider)
            actual = self.temporary.get(name, set())
            if dependency["status"] == "cleaned":
                if actual:
                    self.errors.append(name + ": cleaned but TEMPORARY-DEPENDENCY remains in " + ", ".join(sorted(actual)))
            else:
                declared = set(dependency["marker_paths"])
                for missing in sorted(actual - declared):
                    self.errors.append(name + ": marker path is not registered: " + missing)
                for stale in sorted(declared - actual):
                    self.errors.append(name + ": registered path has no TEMPORARY-DEPENDENCY marker: " + stale)

    def records(self):
        result = []
        for dependency in sorted(self.dependencies.values(), key=lambda item: item["id"]):
            providers = []
            for name in dependency["providers"]:
                provider = self.providers.get(name)
                implementation = provider["implementation"] if provider else None
                providers.append({"id": name, "owner": provider["owner"] if provider else None,
                                  "status": provider["status"] if provider else None,
                                  "revision": implementation["revision"] if implementation else None})
            ready = all(provider["status"] == "integration_ready" for provider in providers)
            if dependency["status"] in ("temporary", "integrating"):
                action = "integrate" if ready else "wait_provider"
            else:
                verified = dependency["verification"]["provider_revisions"]
                same = all(provider["revision"] and verified[provider["id"]].lower() == provider["revision"].lower()
                           for provider in providers)
                action = ("complete" if dependency["status"] == "cleaned" else "cleanup") if ready and same else "reverify"
            result.append(dict(dependency, providers=providers, action=action, complete=action == "complete"))
        return result


def select(records, args):
    return [record for record in records
            if (not args.consumer or record["consumer"] == args.consumer)
            and any((not args.provider or item["id"] == args.provider)
                    and (not args.provider_owner or item["owner"] == args.provider_owner)
                    for item in record["providers"])]


def warning(record):
    actions = {
        "wait_provider": "等待提供方准备；临时依赖仍需跟踪",
        "integrate": "READY / 待接入：提供方已准备，消费方仍有临时依赖，请安排联调",
        "cleanup": "真实联调已登记，待按清单清理临时内容",
        "reverify": "提供方状态或实现版本已变化，需要重新验证；保留原验收历史",
    }
    if record["action"] in actions:
        return "{} [{} / {}]: {}".format(record["id"], record["consumer"], record["owner"], actions[record["action"]])
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--provider", help="筛选提供能力 ID")
    parser.add_argument("--provider-owner", help="筛选提供方主责组，例如 M2")
    parser.add_argument("--consumer", help="筛选消费方，例如 M1")
    parser.add_argument("--require-complete", action="store_true", help="要求指定范围均已清理并针对当前提供版本验证")
    parser.add_argument("--json", action="store_true", help="仅输出 JSON")
    args = parser.parse_args(argv)
    audit = Audit(args.root)
    if audit.errors:
        pass
    elif not audit.root.is_dir():
        audit.errors.append("repository root does not exist or is not a directory")
    else:
        audit.load()
        audit.scan()
    filtered = bool(args.provider or args.provider_owner or args.consumer)
    selection_errors = []
    if args.require_complete and not filtered:
        selection_errors.append("--require-complete requires an explicit --provider, --provider-owner or --consumer filter")
    if args.provider and args.provider not in audit.providers:
        selection_errors.append("unknown provider filter: " + args.provider)
    if args.provider_owner and args.provider_owner not in {item["owner"] for item in audit.providers.values()}:
        selection_errors.append("unknown provider-owner filter: " + args.provider_owner)
    if args.consumer and args.consumer not in audit.consumers:
        selection_errors.append("unknown consumer filter: " + args.consumer)
    selected = select(audit.records(), args)
    if filtered and not selected:
        selection_errors.append("filters matched no dependencies")
    audit.errors.extend(selection_errors)
    warnings = [message for record in selected for message in [warning(record)] if message]
    if args.require_complete and not selection_errors:
        for record in selected:
            if not record["complete"]:
                audit.errors.append(record["id"] + ": --require-complete failed (" + record["action"] + ")")
    visible_provider_ids = {provider["id"] for record in selected for provider in record["providers"]}
    providers = [provider for name, provider in sorted(audit.providers.items())
                 if not filtered or name in visible_provider_ids]
    report = {"providers": providers, "dependencies": selected, "errors": audit.errors, "warnings": warnings}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for provider in providers:
            print("PROVIDER {} owner={} status={}".format(provider["id"], provider["owner"], provider["status"]))
        for record in selected:
            print("DEPENDENCY {} consumer={} owner={} status={} providers={} action={}".format(
                record["id"], record["consumer"], record["owner"], record["status"],
                ",".join(item["id"] for item in record["providers"]), record["action"]))
            print("  inventory: " + record["inventory"])
            print("  marker_paths: " + (", ".join(record["marker_paths"]) or "(none)"))
        for message in warnings:
            print("WARNING: " + message)
            if os.getenv("GITHUB_ACTIONS"):
                escaped = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
                print("::warning::" + escaped)
        for message in audit.errors:
            print("ERROR: " + message, file=sys.stderr)
        print("登记校验：{} 个提供能力，{} 项消费依赖，{} 个错误。文件存在不代表真实联调已通过。".format(
            len(providers), len(selected), len(audit.errors)))
    return 2 if selection_errors else (1 if audit.errors else 0)


if __name__ == "__main__":
    sys.exit(main())
