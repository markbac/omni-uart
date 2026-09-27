"""Release Notes Generator Script based on resolved GitHub Issues & Commit Log."""

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
    """Categorize commits and resolved issue references into structured Release Notes."""
    features = []
    fixes = []
    docs = []
    refactoring = []
    other = []

    issue_pattern = re.compile(r"#(\d+)")

    for line in commits:
        if not line.strip():
            continue
        # Extract issue numbers
        issues = issue_pattern.findall(line)
        issue_str = f" ({', '.join('#' + i for i in issues)})" if issues else ""

        clean_line = line.split(" ", 1)[1] if " " in line else line

        if clean_line.startswith(("feat", "subtask(protocols)", "subtask(ui)", "subtask(entrypoints)", "subtask(build)")):
            features.append(f"- {clean_line}{issue_str}")
        elif clean_line.startswith(("fix", "subtask(cli)")):
            fixes.append(f"- {clean_line}{issue_str}")
        elif clean_line.startswith("docs"):
            docs.append(f"- {clean_line}{issue_str}")
        elif clean_line.startswith("refactor"):
            refactoring.append(f"- {clean_line}{issue_str}")
        else:
            other.append(f"- {clean_line}{issue_str}")

    md_lines = ["## 📋 Resolved Issues & Release Changelog\n"]

    if features:
        md_lines.append("### 🚀 New Features & Enhancements")
        md_lines.extend(features)
        md_lines.append("")

    if fixes:
        md_lines.append("### 🐛 Bug Fixes & Stability Patch Resolutions")
        md_lines.extend(fixes)
        md_lines.append("")

    if docs:
        md_lines.append("### 📖 Documentation & Protocol Specifications")
        md_lines.extend(docs)
        md_lines.append("")

    if refactoring:
        md_lines.append("### 🏗️ Codebase Architecture & Refactoring")
        md_lines.extend(refactoring)
        md_lines.append("")

    if other:
        md_lines.append("### 📦 Maintenance & Build System")
        md_lines.extend(other)
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
