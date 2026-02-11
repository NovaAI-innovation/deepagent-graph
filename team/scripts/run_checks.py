"""Run repository validation checks from one command."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import List


def _run(cmd: List[str], repo_root: str) -> int:
    print(f"==> {' '.join(cmd)}")
    completed = subprocess.run(cmd, cwd=repo_root, check=False)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repository checks")
    parser.add_argument(
        "--with-smoke",
        action="store_true",
        help="Also run a smoke orchestrator execution after validation checks.",
    )
    args = parser.parse_args()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    commands: List[List[str]] = [
        [sys.executable, os.path.join("team", "scripts", "validate_system_profile.py")],
        [sys.executable, os.path.join("team", "scripts", "validate_playbooks.py")],
        [sys.executable, os.path.join("team", "scripts", "validate_templates.py")],
        [sys.executable, os.path.join("team", "scripts", "validate_skills.py")],
        [sys.executable, os.path.join("team", "scripts", "validate_markdown_skills.py")],
        [sys.executable, os.path.join("team", "scripts", "validate_skill_exclusivity.py")],
    ]
    if args.with_smoke:
        commands.append(
            [
                sys.executable,
                os.path.join("team", "orchestrator", "orchestrator.py"),
                "--repo",
                repo_root,
                "--playbook",
                "build",
            ]
        )

    failures = 0
    for cmd in commands:
        exit_code = _run(cmd, repo_root)
        if exit_code != 0:
            failures += 1

    if failures:
        print(f"\nChecks failed: {failures} command(s) reported errors.")
        return 1

    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
