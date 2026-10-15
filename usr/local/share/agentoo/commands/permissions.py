#!/usr/bin/env python3
"""Check or restore permissions for tracked agentoo files and managed directories."""
import argparse
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys

POLICY = "etc/agentoo/permissions.conf"


def validate_relative(relative):
    parts = PurePosixPath(relative).parts
    if (not parts or relative.startswith("/") or ".." in parts
            or str(PurePosixPath(relative)) != relative):
        raise ValueError(f"invalid relative path: {relative}")
    return parts


def open_path(root, relative, directory=False):
    """Walk using directory descriptors; reject symlinks in every component."""
    parts = validate_relative(relative)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in parts[:-1]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=fd)
            os.close(fd)
            fd = child
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        if directory:
            flags |= os.O_DIRECTORY
        leaf = os.open(parts[-1], flags, dir_fd=fd)
        kind = os.fstat(leaf).st_mode
        if not (stat.S_ISDIR(kind) if directory else stat.S_ISREG(kind)):
            os.close(leaf)
            raise ValueError(f"unexpected path type: {relative}")
        return leaf
    finally:
        os.close(fd)


def load_policy(root):
    rules = {}
    fd = open_path(root, POLICY)
    with os.fdopen(fd) as stream:
        lines = stream.read().splitlines()
    for number, line in enumerate(lines, 1):
        fields = line.split()
        if not fields or fields[0].startswith("#"):
            continue
        kind = fields[0]
        if kind not in ("tree", "file", "dir") or len(fields) != (6 if kind == "tree" else 5):
            raise ValueError(f"{POLICY}:{number}: expected tree path uid gid file-mode dir-mode, or file/dir path uid gid mode")
        relative = fields[1]
        if kind != "file":
            relative = relative.removesuffix("/")
        validate_relative(relative)
        key = (kind, relative)
        if key in rules or (kind == "file" and any((k, relative) in rules for k in ("tree", "dir"))) or (kind != "file" and ("file", relative) in rules):
            raise ValueError(f"{POLICY}:{number}: duplicate or conflicting path: {relative}")
        uid, gid = fields[2:4]
        if not uid.isdecimal() or not gid.isdecimal():
            raise ValueError(f"{POLICY}:{number}: owners must be numeric UID/GID")
        modes = fields[4:]
        if any(len(mode) != 4 or any(c not in "01234567" for c in mode)
               or int(mode, 8) & 0o7000 for mode in modes):
            raise ValueError(f"{POLICY}:{number}: invalid mode or special bits")
        rules[key] = (int(uid), int(gid), *(int(mode, 8) for mode in modes))
    if resolve_rule(rules, POLICY) is None:
        raise ValueError("permissions policy must cover itself")
    return rules


def resolve_rule(rules, relative, directory=False):
    exact = rules.get(("dir" if directory else "file", relative))
    if exact is not None:
        return exact
    path = PurePosixPath(relative)
    ancestors = (path, *path.parents) if directory else path.parents
    for ancestor in ancestors:
        rule = rules.get(("tree", str(ancestor)))
        if rule is not None:
            return (*rule[:2], rule[3 if directory else 2])
    return None


def tracked_files(root):
    git_dir = root / "var/lib/agentoo/repository.git"
    if git_dir.is_dir():
        command = ["git", f"--git-dir={git_dir}", f"--work-tree={root}", "-C", str(root)]
    elif (root / ".git").exists():
        command = ["git", "-C", str(root)]
    else:
        raise ValueError("tracked permission rules require the agentoo Git repository")
    result = subprocess.run(command + ["ls-files", "-z"], check=True, stdout=subprocess.PIPE)
    paths = set(os.fsdecode(result.stdout).split("\0")) - {""}
    for path in paths:
        validate_relative(path)
    return paths


def managed_entries(rules, tracked):
    entries = {}
    for kind, relative in rules:
        if kind != "tree":
            entries[(relative, kind == "dir")] = resolve_rule(rules, relative, kind == "dir")
        else:
            entries[(relative, True)] = resolve_rule(rules, relative, True)
    problems = []
    for relative in sorted(tracked):
        expected = resolve_rule(rules, relative)
        if expected is None:
            problems.append(f"no permission policy for tracked file: /{relative}")
            continue
        entries[(relative, False)] = expected
        for parent in PurePosixPath(relative).parents:
            directory = str(parent)
            expected = resolve_rule(rules, directory, True)
            if expected is not None:
                entries[(directory, True)] = expected
    return entries, problems


def main():
    parser = argparse.ArgumentParser(prog="agentoo permissions", description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true", help="report only (default)")
    modes.add_argument("--fix", action="store_true", help="restore declared ownership and modes")
    parser.add_argument("--root", default="/", help="mounted target root (default: /)")
    args = parser.parse_args()
    root = Path(args.root).resolve(strict=True)
    if not root.is_dir():
        parser.error("target root must be a directory")
    if args.fix and os.geteuid() != 0:
        parser.error("--fix requires root; no automatic elevation is performed")
    rules = load_policy(root)
    entries, problems = managed_entries(rules, tracked_files(root))
    changes = []
    for (relative, directory), expected in sorted(entries.items()):
        try:
            fd = open_path(root, relative, directory)
            try:
                current = os.fstat(fd)
            finally:
                os.close(fd)
            actual = (current.st_uid, current.st_gid, stat.S_IMODE(current.st_mode))
            if actual != expected:
                changes.append((relative, directory, expected, (current.st_dev, current.st_ino)))
                print(f"MISMATCH /{relative}: {actual[0]}:{actual[1]} {actual[2]:04o}"
                      f" -> {expected[0]}:{expected[1]} {expected[2]:04o}")
        except (ValueError, OSError) as error:
            problems.append(f"/{relative}: {error}")
    if problems:
        for problem in problems:
            print(f"ERROR {problem}", file=sys.stderr)
        print("No permissions changed: resolve policy/path errors first.", file=sys.stderr)
        return 1
    if args.fix:
        for relative, directory, (uid, gid, mode), identity in changes:
            fd = open_path(root, relative, directory)
            try:
                current = os.fstat(fd)
                if (current.st_dev, current.st_ino) != identity:
                    raise ValueError(f"path changed during permission repair: {relative}")
                os.fchown(fd, uid, gid)
                os.fchmod(fd, mode)
            finally:
                os.close(fd)
        print(f"Permissions: {len(changes)} corrected; {len(entries)} paths checked.")
        return 0
    print(f"Permissions: {len(changes)} mismatches; {len(entries)} paths checked.")
    return int(bool(changes))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"ERROR {error}", file=sys.stderr)
        sys.exit(1)
