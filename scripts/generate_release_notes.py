"""Release Notes Generator Script adhering to Keep a Changelog 1.1.0 Specification."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def get_git_commits_since_last_tag() -> list[str]:
    """Fetch list of commit subject lines since previous tag or all commits."""
    try:
        tags = subprocess.check_output(["git", "tag", "-l", "--sort=-creatordate"], text=True).strip().splitlines()
        if len(tags) > 1:
            prev_tag = tags[1]
            cmd = ["git", "log", f"{prev_tag}..HEAD", "--oneline"]
        else:
            cmd = ["git", "log", "--oneline"]
        output = subprocess.check_output(cmd, text=True).strip()
        return output.splitlines() if output else []
    except Exception:
        return []


def generate_issue_release_notes(commits: list[str]) -> str:
    """Categorize commits and resolved issue references into Keep a Changelog 1.1.0 sections."""
    added = []
    changed = []
    deprecated = []
    removed = []
    fixed = []
    security = []

    issue_pattern = re.compile(r"#(\d+)")

    for line in commits:
        if not line.strip():
            continue

        issues = issue_pattern.findall(line)
        issue_str = f" ({', '.join('#' + i for i in issues)})" if issues else ""

        clean_line = line.split(" ", 1)[1] if " " in line else line

        lowered = clean_line.lower()
        if lowered.startswith(("feat", "subtask(protocols)", "subtask(ui)", "subtask(desktop)", "subtask(entrypoints)")):
            added.append(f"- {clean_line}{issue_str}")
        elif lowered.startswith("fix"):
            fixed.append(f"- {clean_line}{issue_str}")
        elif lowered.startswith(("sec", "subtask(sec)", "security")):
            security.append(f"- {clean_line}{issue_str}")
        elif lowered.startswith("deprecate"):
            deprecated.append(f"- {clean_line}{issue_str}")
        elif lowered.startswith("remove"):
            removed.append(f"- {clean_line}{issue_str}")
        else:
            changed.append(f"- {clean_line}{issue_str}")

    md_lines = ["## Release Notes (Keep a Changelog 1.1.0 Format)\n"]

    if added:
        md_lines.append("### Added")
        md_lines.extend(added)
        md_lines.append("")

    if changed:
        md_lines.append("### Changed")
        md_lines.extend(changed)
        md_lines.append("")

    if deprecated:
        md_lines.append("### Deprecated")
        md_lines.extend(deprecated)
        md_lines.append("")

    if removed:
        md_lines.append("### Removed")
        md_lines.extend(removed)
        md_lines.append("")

    if fixed:
        md_lines.append("### Fixed")
        md_lines.extend(fixed)
        md_lines.append("")

    if security:
        md_lines.append("### Security")
        md_lines.extend(security)
        md_lines.append("")

    return "\n".join(md_lines)


def main() -> int:
    commits = get_git_commits_since_last_tag()
    notes = generate_issue_release_notes(commits)
    output_file = Path("RELEASE_NOTES.md")
    output_file.write_text(notes, encoding="utf-8")
    print(f"Generated Release Notes in {output_file.resolve()}:\n")
    print(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
