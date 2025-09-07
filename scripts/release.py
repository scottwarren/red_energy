#!/usr/bin/env python3
"""
Release helper: bump version in manifest.json, commit, tag, and push.

Usage examples:
  - Patch release:  python scripts/release.py --part patch
  - Minor release:  python scripts/release.py --part minor
  - Major release:  python scripts/release.py --part major
  - Dry run only:   python scripts/release.py --part patch --dry-run

Requires: git CLI in PATH, clean working tree.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "custom_components" / "red_energy" / "manifest.json"


def run(cmd: list[str], dry_run: bool = False) -> None:
    print("$", " ".join(cmd))
    if dry_run:
        return
    subprocess.check_call(cmd, cwd=str(REPO_ROOT))


def get_current_branch() -> str:
    out = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(REPO_ROOT))
    return out.decode().strip()


def ensure_clean_tree() -> None:
    out = subprocess.check_output(["git", "status", "--porcelain"], cwd=str(REPO_ROOT)).decode().strip()
    if out:
        print("Error: Working tree not clean. Commit or stash changes before releasing.")
        print(out)
        sys.exit(2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bump version, tag, and push release")
    parser.add_argument("--part", choices=["patch", "minor", "major"], default="patch")
    parser.add_argument("--remote", default=os.getenv("GIT_REMOTE", "origin"))
    parser.add_argument("--branch", default=os.getenv("RELEASE_BRANCH", "main"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--notes", help="Release notes text")
    parser.add_argument("--notes-file", help="Path to a file with release notes")
    return parser.parse_args()


def read_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        print(f"Error: manifest.json not found at {MANIFEST_PATH}")
        sys.exit(1)
    data = json.loads(MANIFEST_PATH.read_text())
    return data


def write_manifest(manifest: dict, dry_run: bool) -> None:
    text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    if dry_run:
        print("Would write manifest.json:\n" + text)
        return
    MANIFEST_PATH.write_text(text)


def bump_semver(version: str, part: str) -> str:
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        print(f"Error: version '{version}' is not semver X.Y.Z")
        sys.exit(1)
    major, minor, patch = map(int, version.split("."))
    if part == "patch":
        patch += 1
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "major":
        major += 1
        minor = 0
        patch = 0
    return f"{major}.{minor}.{patch}"


def tag_exists(tag: str) -> bool:
    try:
        subprocess.check_call(["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"], cwd=str(REPO_ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False


def main() -> int:
    args = parse_args()

    # Basic safety checks
    current_branch = get_current_branch()
    if current_branch != args.branch:
        print(f"Warning: Current branch is '{current_branch}', expected '{args.branch}'. Proceeding anyway.")
    ensure_clean_tree()

    manifest = read_manifest()
    current_version = str(manifest.get("version", "0.0.0"))
    new_version = bump_semver(current_version, args.part)
    tag = f"v{new_version}"

    if tag_exists(tag):
        print(f"Error: tag {tag} already exists")
        return 3

    # Update manifest
    manifest["version"] = new_version
    write_manifest(manifest, args.dry_run)

    # Commit and tag
    run(["git", "add", str(MANIFEST_PATH.relative_to(REPO_ROOT))], dry_run=args.dry_run)
    run(["git", "commit", "-m", f"chore(release): {tag}"], dry_run=args.dry_run)
    run(["git", "tag", "-a", tag, "-m", f"Release {tag}"], dry_run=args.dry_run)
    run(["git", "push", args.remote, current_branch], dry_run=args.dry_run)
    run(["git", "push", args.remote, tag], dry_run=args.dry_run)

    # Create GitHub Release if gh CLI available
    notes: str | None = None
    if args.notes_file:
        nf = Path(args.notes_file)
        if nf.exists():
            notes = nf.read_text()
        else:
            print(f"Warning: notes file not found: {nf}")
    elif args.notes:
        notes = args.notes
    else:
        notes = f"Automated release {tag}.\n\n- See commit history for details."

    try:
        # Check gh availability
        subprocess.check_call(["gh", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        gh_cmd = [
            "gh", "release", "create", tag,
            "--title", f"Release {tag}",
            "--notes", notes or "",
        ]
        run(gh_cmd, dry_run=args.dry_run)
    except Exception:
        print("gh CLI not available or failed; skipping GitHub Release creation. You can create it manually.")

    print(f"Release complete: {tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


