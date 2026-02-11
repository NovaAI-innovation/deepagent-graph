"""Validate markdown SKILL files and frontmatter filters."""
from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from team.engine.md_skills import validate_markdown_skills
from team.engine.system_profile import load_system_profile, resolve_skills_dir


def main() -> int:
    profile = load_system_profile(REPO_ROOT)
    skills_dir = resolve_skills_dir(REPO_ROOT, profile)
    if not os.path.isdir(skills_dir):
        print(f"FAIL skills directory does not exist: {skills_dir}")
        return 1
    errors = validate_markdown_skills(skills_dir)
    if errors:
        for err in errors:
            print(f"FAIL {err}")
        print(f"\n{len(errors)} markdown skill validation error(s) found.")
        return 1
    print("All markdown skills passed validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
