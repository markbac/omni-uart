#!/usr/bin/env python3
"""Check the markdown files listed in a docs-as-code YAML manifest.

Runs three independent passes over each file:

1. Markdown structure (markdownlint) - headings, lists, code fences,
   trailing whitespace, in-file link fragments. Config: .markdownlint.yaml
2. Prose (Vale) - Microsoft, Google, proselint, alex, and AiTells, layered
   with the project's own Embedded style (styles/Embedded). Config: .vale.ini
3. Project-specific structural checks that neither tool covers, driven by
   structure-rules.yaml (a small generic rule engine, not hardcoded checks):
   manifest entries exist on disk, cross-file link targets exist, no bare
   horizontal rules in body text, this project's callout format, and no
   blank lines between list items.

Every finding is a warning: nothing here fails the build (exit code is
always 0). Point CI or a pre-commit hook at this script and read the
report, or add a `--fail-on error` flag yourself if you later want it
to gate a build.

Usage:
    python3 check_docs.py path/to/ICD-001-lwm2m.yaml
    python3 check_docs.py path/to/ICD-001-lwm2m.yaml --no-vale --no-markdownlint --no-structure
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
VALE_CONFIG = SCRIPT_DIR / ".vale.ini"
MARKDOWNLINT_CONFIG = SCRIPT_DIR / ".markdownlint.yaml"


@dataclass
class Finding:
    file: Path
    line: int
    severity: str  # "suggestion" | "warning" | "error"
    rule: str
    message: str
    column: int = 0  # 1-indexed character position of the match, when known (0 = unknown)


# --------------------------------------------------------------------------
# Manifest loading
# --------------------------------------------------------------------------

def resolve_target_files(path: Path) -> tuple[list[Path], Path | None]:
    """Returns (files_to_check, manifest_used). path may be a manifest
    (checked directly) or an .md file (checked on its own, with no
    manifest lookup - cross-file checks will only see this one file)."""
    if path.suffix.lower() in (".md", ".markdown"):
        if not path.exists():
            print(f"error: file not found: {path}", file=sys.stderr)
            return [], None
        return [path.resolve()], None
    return load_manifest_files(path), path


def load_manifest_files(manifest_path: Path) -> list[Path]:
    """Return the markdown files listed under `entries:` in the manifest,
    resolved relative to the manifest's own directory."""
    if not manifest_path.exists():
        print(f"error: manifest not found: {manifest_path}", file=sys.stderr)
        return []

    with manifest_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    entries = data.get("entries", [])
    base = manifest_path.parent
    files = []
    for entry in entries:
        rel = entry.get("file")
        if not rel:
            continue
        files.append((base / rel).resolve())
    return files


# --------------------------------------------------------------------------
# Project-specific structural checks
#
# Deliberately narrow: anything markdownlint or Vale already covers well
# (heading hierarchy, list-marker consistency, fenced-code language,
# trailing whitespace, in-file link fragments, ...) lives there instead of
# being reimplemented here. What IS handled here is driven entirely by
# structure-rules.yaml - this is a small generic engine for a handful of
# rule types, not a place to hardcode new checks.
# --------------------------------------------------------------------------

STRUCTURE_RULES_CONFIG = SCRIPT_DIR / "structure-rules.yaml"
FENCE_RE = re.compile(r"^(```|~~~)")
URL_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


@dataclass
class StructureRule:
    id: str
    type: str
    severity: str
    message: str
    pattern: re.Pattern | None = None
    exclude_pattern: re.Pattern | None = None
    scope_prefix: str | None = None
    open_pattern: re.Pattern | None = None
    close_pattern: re.Pattern | None = None
    unmatched_open_message: str | None = None
    unmatched_close_message: str | None = None
    block: str | None = None
    languages: list[str] | None = None
    div_languages: list[str] | None = None
    trigger_pattern: re.Pattern | None = None
    collision_severity: str | None = None
    collision_message: str | None = None


def load_structure_rules() -> list[StructureRule]:
    if not STRUCTURE_RULES_CONFIG.exists():
        print(f"warning: no {STRUCTURE_RULES_CONFIG} - skipping project-specific structural checks.",
              file=sys.stderr)
        return []
    with STRUCTURE_RULES_CONFIG.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    rules = []
    for entry in data.get("rules", []):
        if not entry.get("enabled", True):
            continue
        pattern_src = entry.get("pattern") or entry.get("required_pattern")
        rules.append(StructureRule(
            id=entry["id"],
            type=entry["type"],
            severity=entry.get("severity", "warning"),
            message=entry.get("message", ""),
            pattern=re.compile(pattern_src) if pattern_src else None,
            exclude_pattern=re.compile(entry["exclude_pattern"]) if "exclude_pattern" in entry else None,
            scope_prefix=entry.get("scope_prefix"),
            open_pattern=re.compile(entry["open_pattern"]) if "open_pattern" in entry else None,
            close_pattern=re.compile(entry["close_pattern"]) if "close_pattern" in entry else None,
            unmatched_open_message=entry.get("unmatched_open_message"),
            unmatched_close_message=entry.get("unmatched_close_message"),
            block=entry.get("block"),
            languages=[lang.lower() for lang in entry["languages"]] if "languages" in entry else None,
            div_languages=[lang.lower() for lang in entry["div_languages"]] if "div_languages" in entry else None,
            trigger_pattern=re.compile(entry["trigger_pattern"]) if "trigger_pattern" in entry else None,
            collision_severity=entry.get("collision_severity"),
            collision_message=entry.get("collision_message"),
        ))
    return rules


def _iter_non_fenced_lines(lines: list[str]):
    """Yield (line_no, line) for every line outside fenced code blocks."""
    in_fence = False
    fence_marker = ""
    for i, line in enumerate(lines, start=1):
        fence_m = FENCE_RE.match(line)
        if fence_m and not in_fence:
            in_fence, fence_marker = True, fence_m.group(1)
            continue
        if in_fence:
            if line.startswith(fence_marker):
                in_fence = False
            continue
        yield i, line


BACKTICK_SPAN_RE = re.compile(r"`[^`]*`")


def _backtick_spans(line: str) -> list[tuple[int, int]]:
    """Spans of inline code on a line - matches inside these are being
    shown as literal text (a syntax example), not live directives."""
    return [m.span() for m in BACKTICK_SPAN_RE.finditer(line)]


def _in_any_span(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= pos < end for start, end in spans)


def _check_balanced_markers(path: Path, lines: list[str], rule: StructureRule) -> list[Finding]:
    stack: list[tuple[int, str]] = []
    findings: list[Finding] = []
    for i, line in _iter_non_fenced_lines(lines):
        spans = _backtick_spans(line)
        # Process opens and closes in the order they appear on the line.
        events = [(m.start(), "open", m.group(0)) for m in rule.open_pattern.finditer(line)
                  if not _in_any_span(m.start(), spans)]
        events += [(m.start(), "close", m.group(0)) for m in rule.close_pattern.finditer(line)
                   if not _in_any_span(m.start(), spans)]
        for _, kind, text in sorted(events, key=lambda e: e[0]):
            if kind == "open":
                stack.append((i, text))
            elif stack:
                stack.pop()
            else:
                msg = (rule.unmatched_close_message or rule.message).format(marker=text)
                findings.append(Finding(path, i, rule.severity, rule.id, msg))
    for line_no, text in stack:
        msg = (rule.unmatched_open_message or rule.message).format(marker=text)
        findings.append(Finding(path, line_no, rule.severity, rule.id, msg))
    return findings


TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
# Matches ``` / ~~~ fences with a language info-string, or a pandoc fenced
# div (:::name or ::: {.name ...}) - covers both how Vale/markdownlint see
# code fences and how this project's Mermaid blocks are written.
FENCE_OPEN_RE = re.compile(r"^(```+|~~~+|:::+)\s*\{?\.?([A-Za-z0-9_-]*)")


def _check_caption_rules(path: Path, lines: list[str],
                          table_rule: StructureRule | None,
                          image_rule: StructureRule | None,
                          fence_rule: StructureRule | None,
                          line_rules: list[StructureRule]) -> list[Finding]:
    """Table, image, code-fence, and single-line-trigger blocks (like
    [[INCLUDE-CODE: ...]]) each need a caption marker on the line
    immediately after them. Runs as a single coordinated pass so
    table/image detection correctly skips over anything shown inside an
    unrelated code fence.

    For fence_rule: ``` / ~~~ code fences require a caption for every
    language (or no language) unless `languages` narrows that down -
    since "every code block" includes plain examples, not just diagrams.
    ::: fenced divs are different: those are used for non-diagram things
    too (e.g. `::: {.pagebreak}`), so a div only needs a caption if its
    class is explicitly listed in `div_languages` (e.g. mermaid).

    For line_rules (block: line): `trigger_pattern` matches a single
    line (not a multi-line block) - e.g. an [[INCLUDE-CODE:]] directive -
    and that one line needs a caption right after it, same as a table."""
    findings: list[Finding] = []
    n = len(lines)
    fence_langs = set(fence_rule.languages) if fence_rule and fence_rule.languages else set()
    div_langs = set(fence_rule.div_languages) if fence_rule and fence_rule.div_languages else set()

    def caption_present(after_idx: int, required: re.Pattern) -> bool:
        j = after_idx
        while j < n and lines[j].strip() == "":
            j += 1
        # search, not match: your docs use both '[[CAPTION:Figure]] text'
        # and 'text[[CAPTION:Figure]]' (marker at the end, no space) - the
        # marker can be anywhere on the line, not just at the start.
        return j < n and bool(required.search(lines[j]))

    i = 0
    while i < n:
        line = lines[i]
        fence_m = FENCE_OPEN_RE.match(line)
        if fence_m:
            marker, lang = fence_m.group(1), fence_m.group(2).lower()
            j = i + 1
            while j < n and not lines[j].startswith(marker):
                j += 1
            is_div = marker.startswith(":")
            needs_caption = (lang in div_langs) if is_div else (not fence_langs or lang in fence_langs)
            if fence_rule and needs_caption and not caption_present(j + 1, fence_rule.pattern):
                findings.append(Finding(path, min(j + 1, n), fence_rule.severity,
                                         fence_rule.id, fence_rule.message))
            i = j + 1
            continue
        if table_rule and TABLE_ROW_RE.match(line):
            while i < n and TABLE_ROW_RE.match(lines[i]):
                i += 1
            if not caption_present(i, table_rule.pattern):
                findings.append(Finding(path, i, table_rule.severity, table_rule.id, table_rule.message))
            continue
        if image_rule and IMAGE_RE.search(line):
            if not caption_present(i + 1, image_rule.pattern):
                findings.append(Finding(path, i + 1, image_rule.severity, image_rule.id, image_rule.message))
        for rule in line_rules:
            if rule.trigger_pattern.search(line) and not caption_present(i + 1, rule.pattern):
                findings.append(Finding(path, i + 1, rule.severity, rule.id, rule.message))
        i += 1

    return findings


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)")
SLUG_STRIP_RE = re.compile(r"[^\w\- ]")
INLINE_FORMAT_RE = re.compile(r"[`*_]")
LINK_TEXT_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
ANCHOR_LINK_RE = re.compile(r"!?\[[^\]]*\]\(#([^)\s]+)\)")


def _slugify(text: str) -> str:
    """Approximates pandoc's auto_identifiers heading-anchor algorithm:
    lowercase, strip everything except word chars/hyphens/spaces, spaces
    become hyphens. Verified against real headings from this project's
    documents (e.g. '11000/0 - Daily Volume Profile (R6029)' ->
    '110000---daily-volume-profile-r6029')."""
    plain = INLINE_FORMAT_RE.sub("", text)
    plain = LINK_TEXT_RE.sub(r"\1", plain)
    return SLUG_STRIP_RE.sub("", plain).strip().lower().replace(" ", "-")


def check_cross_file_anchors(files: list[Path], rules: list[StructureRule]) -> list[Finding]:
    """Runs once across the whole file set, not per-file. When several
    files get concatenated into one pandoc build, all their headings
    share a single anchor namespace: the second file with a heading
    identical to an earlier one gets its anchor auto-suffixed ('-1',
    '-2', ...) in document order. Neither markdownlint nor Vale can see
    this, since each only ever looks at one file at a time - this can
    both flag legitimate cross-file links that markdownlint's MD051
    wrongly calls broken, and catch a class of bug MD051 can't see at
    all: a link written for a heading that pandoc silently renamed out
    from under it because an earlier file already claimed that anchor."""
    cf_rules = [r for r in rules if r.type == "cross-file-anchors"]
    if not cf_rules:
        return []

    occurrences: list[tuple[Path, int, str]] = []  # (file, line, base_slug)
    file_lines: dict[Path, list[str]] = {}
    for path in files:
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        file_lines[path] = lines
        for i, line in _iter_non_fenced_lines(lines):
            hm = HEADING_RE.match(line)
            if hm:
                occurrences.append((path, i, _slugify(hm.group(2).strip())))

    # Assign resolved anchors in document order, matching pandoc's
    # disambiguation: first occurrence of a slug keeps it plain, every
    # later occurrence gets '-1', '-2', ... appended.
    seen_count: dict[str, int] = {}
    by_slug: dict[str, list[tuple[Path, int, str]]] = {}
    anchor_registry: set[str] = set()
    for path, line, base_slug in occurrences:
        n = seen_count.get(base_slug, 0)
        resolved = base_slug if n == 0 else f"{base_slug}-{n}"
        seen_count[base_slug] = n + 1
        anchor_registry.add(resolved)
        by_slug.setdefault(base_slug, []).append((path, line, resolved))

    findings: list[Finding] = []
    for rule in cf_rules:
        if rule.collision_message:
            for base_slug, occs in by_slug.items():
                if len(occs) > 1:
                    first_file = occs[0][0]
                    for path, line, _resolved in occs[1:]:
                        msg = rule.collision_message.format(target=base_slug, other_file=first_file.name)
                        findings.append(Finding(path, line, rule.collision_severity or rule.severity,
                                                 rule.id, msg))

        for path, lines in file_lines.items():
            for i, line in _iter_non_fenced_lines(lines):
                spans = _backtick_spans(line)
                for m in ANCHOR_LINK_RE.finditer(line):
                    if _in_any_span(m.start(), spans):
                        continue
                    target = m.group(1)
                    if target not in anchor_registry:
                        findings.append(Finding(path, i, rule.severity, rule.id,
                                                 rule.message.format(target=target)))

    return findings


def check_structure(path: Path, rules: list[StructureRule]) -> list[Finding]:
    file_rule = next((r for r in rules if r.type == "manifest-file-exists"), None)
    if not path.exists():
        return [Finding(path, 0, file_rule.severity, file_rule.id, file_rule.message)] if file_rule else []

    regex_rules = [r for r in rules if r.type == "regex-line"]
    blank_rules = [r for r in rules if r.type == "blank-line-between"]
    path_rules = [r for r in rules if r.type == "path-exists"]
    balance_rules = [r for r in rules if r.type == "balanced-markers"]
    caption_rules = [r for r in rules if r.type == "requires-caption"]

    findings: list[Finding] = []
    lines = path.read_text(encoding="utf-8").splitlines()

    for i, line in _iter_non_fenced_lines(lines):
        spans = _backtick_spans(line)

        for rule in regex_rules:
            if rule.scope_prefix and not line.startswith(rule.scope_prefix):
                continue
            for m in rule.pattern.finditer(line):
                if _in_any_span(m.start(), spans):
                    continue
                if rule.exclude_pattern and rule.exclude_pattern.search(line):
                    continue
                findings.append(Finding(path, i, rule.severity, rule.id, rule.message))
                break  # one finding per rule per line

        # Flag the first blank line of a run that separates two lines both
        # matching the rule's pattern (e.g. two list items) - only once per
        # gap, so a multi-blank gap isn't reported multiple times.
        if line.strip() == "" and i >= 2 and lines[i - 2].strip() != "":
            for rule in blank_rules:
                if not rule.pattern.match(lines[i - 2]):
                    continue
                j = i  # 0-indexed position of the next line after this blank
                while j < len(lines) and lines[j].strip() == "":
                    j += 1
                if j < len(lines) and rule.pattern.match(lines[j]):
                    findings.append(Finding(path, i, rule.severity, rule.id, rule.message))

        for rule in path_rules:
            for m in rule.pattern.finditer(line):
                if _in_any_span(m.start(), spans):
                    continue
                target = m.group(1).strip()
                if URL_SCHEME_RE.match(target) or target.startswith("#"):
                    continue  # external URL, or in-file anchor - markdownlint (MD051) checks anchors
                target_path = target.split("#", 1)[0]
                if target_path and not (path.parent / target_path).exists():
                    findings.append(Finding(path, i, rule.severity, rule.id,
                                             rule.message.format(target=target_path)))

    for rule in balance_rules:
        findings.extend(_check_balanced_markers(path, lines, rule))

    if caption_rules:
        table_rule = next((r for r in caption_rules if r.block == "table"), None)
        image_rule = next((r for r in caption_rules if r.block == "image"), None)
        fence_rule = next((r for r in caption_rules if r.block == "fence"), None)
        line_rules = [r for r in caption_rules if r.block == "line"]
        findings.extend(_check_caption_rules(path, lines, table_rule, image_rule, fence_rule, line_rules))

    return findings


# --------------------------------------------------------------------------
# Markdown structure (markdownlint)
# --------------------------------------------------------------------------

def check_markdownlint(paths: list[Path], bin_path_arg: str | None) -> list[Finding]:
    bin_path = bin_path_arg or os.environ.get("MARKDOWNLINT_BIN") or shutil.which("markdownlint")
    if not bin_path:
        print("warning: 'markdownlint' not found on PATH - skipping markdown structure checks. "
              "Pass --markdownlint-bin <path> or set MARKDOWNLINT_BIN if it's installed but not "
              "on PATH. See README.md for install instructions.", file=sys.stderr)
        return []
    if not MARKDOWNLINT_CONFIG.exists():
        print(f"warning: no .markdownlint.yaml at {MARKDOWNLINT_CONFIG} - skipping.", file=sys.stderr)
        return []

    existing = [str(p) for p in paths if p.exists()]
    if not existing:
        return []

    result = subprocess.run(
        [bin_path, "-c", str(MARKDOWNLINT_CONFIG), "--json", *existing],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    # markdownlint-cli writes its --json output to stderr, not stdout.
    stderr = result.stderr or ""
    if not stderr.strip():
        return []
    try:
        alerts = json.loads(stderr)
    except json.JSONDecodeError:
        print(f"warning: could not parse markdownlint output: {stderr[:200]}", file=sys.stderr)
        return []

    return [
        Finding(Path(a["fileName"]), a["lineNumber"], "warning",
                "/".join(a["ruleNames"][:2]),
                a["ruleDescription"] + (f" ({a['errorDetail']})" if a.get("errorDetail") else ""),
                column=(a["errorRange"][0] if a.get("errorRange") else 0))
        for a in alerts
    ]


# --------------------------------------------------------------------------
# Prose checks (Vale)
# --------------------------------------------------------------------------

def _find_winget_vale() -> str | None:
    """Fall back to vale's WinGet install location on Windows, since the
    'Links' PATH shim doesn't always get created or picked up. Only
    relevant on Windows; a no-op elsewhere."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return None
    matches = glob.glob(
        os.path.join(local_app_data, "Microsoft", "WinGet", "Packages", "errata-ai.Vale_*", "vale.exe"))
    return matches[0] if matches else None


def _derived_vale_config(base_config: Path, requirements_mode: bool, disable_rules: list[str]) -> Path:
    """Derive a Vale config from .vale.ini for this run's --requirements
    and --disable-rule flags, so .vale.ini itself stays the single file
    to hand-edit and neither flag needs to touch it. A no-op (returns
    base_config unchanged) when neither flag is used."""
    if not requirements_mode and not disable_rules:
        return base_config

    text = base_config.read_text(encoding="utf-8")

    if requirements_mode:
        requirements_dir = SCRIPT_DIR / "styles" / "Requirements"
        if not requirements_dir.is_dir() or not any(requirements_dir.glob("*.yml")):
            print(f"warning: --requirements was passed but {requirements_dir} has no .yml rule "
                  "files - running WITHOUT Requirements mode instead of failing the whole prose "
                  "pass. Put AmbiguousWords.yml / LongRequirement.yml / ModalConsistency.yml / "
                  "PlainLanguage.yml there to enable it.", file=sys.stderr)
        else:
            def add_requirements(m: re.Match) -> str:
                styles = [s.strip() for s in m.group(1).split(",")]
                if "Requirements" not in styles:
                    styles.append("Requirements")
                return "BasedOnStyles = " + ", ".join(styles)

            new_text, count = re.subn(r"BasedOnStyles\s*=\s*(.+)", add_requirements, text)
            if count == 0:
                print(f"warning: no BasedOnStyles line found in {base_config} - "
                      "--requirements has nothing to add to.", file=sys.stderr)
            else:
                text = new_text

    if disable_rules:
        text += "\n\n# --disable-rule (this run only, not saved to .vale.ini)\n"
        for rule in disable_rules:
            text += f"{rule} = NO\n"

    # Written alongside .vale.ini so its relative StylesPath still resolves.
    out_path = base_config.parent / ".vale.generated.ini"
    out_path.write_text(text, encoding="utf-8")
    return out_path


ACRONYM_DEFINITION_RE = re.compile(r"(?:\b[A-Z][a-z]+ )+\(([A-Z]{2,6}[0-9]?)\)")


def _dedupe_acronym_findings(findings: list[Finding]) -> list[Finding]:
    """Vale's Embedded.Acronyms flags every bare occurrence of an
    undefined acronym individually, which is noisy for a term used many
    times. Collapse each (file, acronym) group down to a single finding
    at its first occurrence, and check the source text for whether a
    proper definition ('Word Word (ACRONYM)') exists later in the file -
    if so, say so specifically (move the definition earlier) rather than
    the generic 'no expansion nearby' message, which is misleading once
    a definition does exist somewhere."""
    groups: dict[tuple[Path, str], list[Finding]] = {}
    other: list[Finding] = []
    for f in findings:
        if f.rule != "Embedded.Acronyms":
            other.append(f)
            continue
        m = re.search(r"'([A-Z0-9]+)'", f.message)
        if not m:
            other.append(f)
            continue
        groups.setdefault((f.file, m.group(1)), []).append(f)

    file_text_cache: dict[Path, str] = {}
    collapsed: list[Finding] = []
    for (path, acronym), group in groups.items():
        group.sort(key=lambda x: x.line)
        first = group[0]
        count = len(group)

        if path not in file_text_cache:
            try:
                file_text_cache[path] = path.read_text(encoding="utf-8")
            except OSError:
                file_text_cache[path] = ""
        text = file_text_cache[path]

        defined_line = None
        for i, line in enumerate(text.splitlines(), start=1):
            dm = ACRONYM_DEFINITION_RE.search(line)
            if dm and dm.group(1) == acronym:
                defined_line = i
                break

        if defined_line is not None:
            times = "once" if count == 1 else f"{count} times"
            message = (f"'{acronym}' is used {times} before it's defined at line {defined_line} "
                       f"- move the definition earlier, or define it on first use instead.")
        else:
            times = "" if count == 1 else f" ({count} occurrences in this file)"
            message = (f"'{acronym}' has no expansion anywhere in this file{times}. "
                       f"Define it on first use, e.g. 'Interface Control Document (ICD)'.")

        collapsed.append(Finding(first.file, first.line, first.severity, first.rule, message,
                                  column=first.column))

    return other + collapsed


def check_prose(paths: list[Path], vale_bin_arg: str | None, requirements_mode: bool = False,
                 disable_rules: list[str] | None = None) -> list[Finding]:
    vale_bin = vale_bin_arg or os.environ.get("VALE_BIN") or shutil.which("vale")
    if not vale_bin:
        vale_bin = _find_winget_vale()
        if vale_bin:
            print(f"warning: 'vale' not on PATH - falling back to WinGet install at {vale_bin}",
                  file=sys.stderr)
    if not vale_bin:
        print("warning: 'vale' not found on PATH - skipping prose checks. "
              "Pass --vale-bin <path> or set VALE_BIN if it's installed but not "
              "on PATH. See README.md for install instructions.", file=sys.stderr)
        return []
    if not VALE_CONFIG.exists():
        print(f"warning: no .vale.ini at {VALE_CONFIG} - skipping prose checks.", file=sys.stderr)
        return []

    config_path = _derived_vale_config(VALE_CONFIG, requirements_mode, disable_rules or [])

    existing = [str(p) for p in paths if p.exists()]
    if not existing:
        return []

    result = subprocess.run(
        [vale_bin, "--config", str(config_path), "--output=JSON", *existing],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(SCRIPT_DIR),
    )
    stdout = result.stdout or ""
    if not stdout.strip():
        if result.returncode not in (0, 1):
            print(f"warning: vale exited unexpectedly ({result.returncode}) - ALL prose checks "
                  f"(Microsoft/Google/proselint/alex/AiTells/Embedded) were skipped for this "
                  f"entire run, not just one file. Details: {result.stderr}", file=sys.stderr)
        return []

    data = json.loads(stdout)
    findings: list[Finding] = []
    for file_str, alerts in data.items():
        for alert in alerts:
            findings.append(Finding(
                Path(file_str), alert["Line"], alert["Severity"],
                f"{alert['Check']}", alert["Message"],
                column=(alert["Span"][0] if alert.get("Span") else 0),
            ))
    return _dedupe_acronym_findings(findings)


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

SEVERITY_ORDER = {"error": 0, "warning": 1, "suggestion": 2}

# ANSI SGR codes - kept dependency-free rather than pulling in colorama.
_RESET = "\033[0m"
_BOLD = "1"
_DIM = "2"
_SEVERITY_FG = {"error": "31", "warning": "33", "suggestion": "36"}  # red, yellow, cyan
_SOURCE_FG = {"markdownlint": "34", "vale": "35", "structure": "32"}  # blue, magenta, green


def _source_of(rule: str) -> str:
    if rule.startswith("structure/"):
        return "structure"
    if re.match(r"^MD\d{3}\b", rule):
        return "markdownlint"
    return "vale"


def _use_color(no_color_flag: bool) -> bool:
    if no_color_flag or os.environ.get("NO_COLOR") is not None:
        return False
    return sys.stdout.isatty()


def _make_source_line_lookup():
    """Returns a function that reads and caches file lines, so both the
    console report and the CSV export can pull the actual source line a
    finding refers to without each re-reading files from scratch."""
    line_cache: dict[Path, list[str]] = {}
    MAX_LEN = 120

    def source_line(path: Path, line_no: int, column: int = 0) -> str | None:
        if line_no < 1:
            return None
        if path not in line_cache:
            try:
                line_cache[path] = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                line_cache[path] = []
        lines = line_cache[path]
        if line_no > len(lines):
            return None
        raw = lines[line_no - 1]
        stripped = raw.strip()
        if len(stripped) <= MAX_LEN:
            return stripped

        # Long line: without a known match position, showing the start is
        # the best we can do. With one, centre the snippet on the actual
        # match instead - otherwise every finding on the same long line
        # (a common case: one long bullet with several issues in it)
        # shows the identical, unhelpful prefix.
        leading_ws = len(raw) - len(raw.lstrip())
        pos = column - 1 - leading_ws if column > 0 else -1
        if pos < 0 or pos >= len(stripped):
            return stripped[: MAX_LEN - 3] + "..."

        half = MAX_LEN // 2
        start = max(0, pos - half)
        end = min(len(stripped), start + MAX_LEN)
        start = max(0, end - MAX_LEN)
        snippet = stripped[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(stripped):
            snippet = snippet + "..."
        return snippet

    return source_line


def print_report(findings: list[Finding], color: bool) -> None:
    if not findings:
        print("No findings.")
        return

    def c(text: str, *codes: str) -> str:
        return f"\033[{';'.join(codes)}m{text}{_RESET}" if color and codes else text

    by_file: dict[Path, list[Finding]] = {}
    for f in findings:
        by_file.setdefault(f.file, []).append(f)

    source_line = _make_source_line_lookup()

    counts_by_severity = {"error": 0, "warning": 0, "suggestion": 0}
    counts_by_source = {"markdownlint": 0, "vale": 0, "structure": 0}
    file_totals: dict[Path, dict[str, int]] = {}
    name_width = min(max((len(f.name) for f in by_file), default=0), 40)

    for file, file_findings in sorted(by_file.items()):
        print(f"\n{file}")
        file_counts = {"error": 0, "warning": 0, "suggestion": 0}
        for f in sorted(file_findings, key=lambda x: (x.line, SEVERITY_ORDER.get(x.severity, 9))):
            source = _source_of(f.rule)
            counts_by_severity[f.severity] = counts_by_severity.get(f.severity, 0) + 1
            counts_by_source[source] = counts_by_source.get(source, 0) + 1
            file_counts[f.severity] = file_counts.get(f.severity, 0) + 1

            file_label = c(f"{file.name:<{name_width}}", _DIM)
            position = f"{f.line}:{f.column}" if f.column > 0 else str(f.line)
            severity_label = c(f"{f.severity:<10}", _BOLD, _SEVERITY_FG[f.severity])
            source_label = c(f"{source:<12}", _SOURCE_FG[source])
            rule_label = c(f"{f.rule:<32}", _SOURCE_FG[source])
            message = c(f.message, _SEVERITY_FG[f.severity])
            print(f"  {file_label} {position:>10}  [{severity_label}] {source_label} {rule_label} {message}")

            snippet = source_line(file, f.line, f.column)
            if snippet:
                print(c(f"  {' ' * name_width}             > {snippet}", _DIM))

        file_total = sum(file_counts.values())
        print("  " + c(f"— {file_total} findings", _BOLD) + " (" + ", ".join(
            c(f"{n} {sev}", _SEVERITY_FG[sev]) for sev, n in file_counts.items()) + ")")
        file_totals[file] = file_counts

    total = sum(counts_by_severity.values())
    print(f"\n{c('Summary', _BOLD)}")
    print("  by severity: " + "  ".join(
        c(f"{n} {sev}", _BOLD, _SEVERITY_FG[sev]) for sev, n in counts_by_severity.items()))
    print("  by source:   " + "  ".join(
        c(f"{n} {src}", _SOURCE_FG[src]) for src, n in counts_by_source.items()))
    if len(file_totals) > 1:
        print("  by file:")
        file_name_width = min(max(len(f.name) for f in file_totals), 40)
        for file, counts in sorted(file_totals.items()):
            file_total = sum(counts.values())
            print(f"    {c(f'{file.name:<{file_name_width}}', _DIM)}  " + c(f"{file_total:>5} total", _BOLD)
                  + "  (" + ", ".join(c(f"{n} {sev}", _SEVERITY_FG[sev]) for sev, n in counts.items()) + ")")
    print(f"\n{total} findings across {len(by_file)} file(s) "
          f"- warnings only, build not failed.")


def write_csv(findings: list[Finding], csv_path: Path) -> None:
    by_file: dict[str, dict[str, int]] = {}
    by_rule: dict[str, dict[str, int | str]] = {}
    for finding in findings:
        file_counts = by_file.setdefault(str(finding.file), {"error": 0, "warning": 0, "suggestion": 0})
        file_counts[finding.severity] = file_counts.get(finding.severity, 0) + 1

        rule_counts = by_rule.setdefault(finding.rule, {"count": 0, "source": _source_of(finding.rule)})
        rule_counts["count"] += 1

    try:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["file", "line", "column", "severity", "source", "rule", "message", "source_line"])
            source_line = _make_source_line_lookup()
            for finding in sorted(findings, key=lambda x: (str(x.file), x.line)):
                writer.writerow([str(finding.file), finding.line, finding.column or "", finding.severity,
                                  _source_of(finding.rule), finding.rule, finding.message,
                                  source_line(finding.file, finding.line, finding.column) or ""])

            # Per-file summary, per-rule summary, then a grand total - same
            # shape as the terminal report's "Summary" block, so the CSV
            # alone tells the full story without the console output too.
            writer.writerow([])
            writer.writerow(["file", "errors", "warnings", "suggestions", "total"])
            totals = {"error": 0, "warning": 0, "suggestion": 0}
            for file, counts in sorted(by_file.items()):
                total = sum(counts.values())
                writer.writerow([file, counts["error"], counts["warning"], counts["suggestion"], total])
                for sev in totals:
                    totals[sev] += counts[sev]
            writer.writerow(["TOTAL", totals["error"], totals["warning"], totals["suggestion"],
                              sum(totals.values())])

            writer.writerow([])
            writer.writerow(["rule", "source", "count"])
            for rule, info in sorted(by_rule.items(), key=lambda kv: kv[1]["count"], reverse=True):
                writer.writerow([rule, info["source"], info["count"]])
    except PermissionError:
        print(f"warning: could not write {csv_path} - permission denied. "
              f"The file is most likely open in another program (e.g. Excel) - "
              f"close it there and run this again.", file=sys.stderr)
        return
    except OSError as e:
        print(f"warning: could not write {csv_path}: {e}", file=sys.stderr)
        return

    print(f"Wrote {len(findings)} findings ({len(by_file)} file(s)) to {csv_path}", file=sys.stderr)


def write_editor_format(findings: list[Finding]) -> None:
    """One line per finding, 'path:line:col: severity: [rule] message' -
    matches what editor tooling (VS Code tasks, most 'jump to problem'
    integrations) expects to parse. Printed to stdout instead of the
    normal grouped report; nothing else is printed in this mode."""
    # VS Code's Problems panel recognises exactly these three severity
    # words for a custom problem matcher; 'suggestion' isn't one of them.
    severity_map = {"error": "error", "warning": "warning", "suggestion": "info"}
    for finding in sorted(findings, key=lambda x: (str(x.file), x.line, x.column)):
        column = finding.column or 1
        severity = severity_map.get(finding.severity, "warning")
        print(f"{finding.file}:{finding.line}:{column}: {severity}: [{finding.rule}] {finding.message}")


def main() -> int:
    # Windows consoles often default to a legacy codepage; force UTF-8 so
    # non-ASCII text in messages (em dashes, accented names, ...) doesn't
    # come out as mojibake.
    if os.name == "nt":
        os.system("")  # enables ANSI escape processing on older Windows consoles
        try:
            # Also switch the console's own codepage to UTF-8. Without this,
            # reconfiguring Python's stream encoding alone isn't enough - the
            # console still expects e.g. cp1252/cp850 and renders incoming
            # UTF-8 bytes as mojibake (e.g. an em dash showing as 'â€“').
            import ctypes
            ctypes.windll.kernel32.SetConsoleCP(65001)
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except (AttributeError, OSError):
            pass

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("manifest", type=Path,
                         help="Path to the docs-as-code YAML manifest, or a single .md file "
                              "(checked on its own; cross-file checks only see that one file)")
    parser.add_argument("--no-vale", action="store_true", help="Skip Vale prose checks")
    parser.add_argument("--no-markdownlint", action="store_true", help="Skip markdownlint structure checks")
    parser.add_argument("--vale-bin", help="Path to the vale executable, if not on PATH")
    parser.add_argument("--markdownlint-bin", help="Path to the markdownlint executable, if not on PATH")
    parser.add_argument("--no-color", action="store_true", help="Disable coloured output")
    parser.add_argument("--no-structure", action="store_true", help="Skip project-specific structural checks")
    parser.add_argument("--csv", type=Path, help="Also write findings to this CSV file")
    parser.add_argument("--requirements", action="store_true",
                         help="Also run Requirements-mode Vale rules (ambiguous words, long "
                              "requirement sentences, MUST/SHALL consistency, plain language)")
    parser.add_argument("--editor-format", action="store_true",
                         help="Print 'path:line:col: severity: [rule] message', one per line, "
                              "for editor/IDE tooling (e.g. a VS Code task problem matcher) "
                              "instead of the normal grouped report")
    parser.add_argument("--disable-rule", action="append", default=[],
                         help="Disable a Vale rule for this run only (e.g. Embedded.Acronyms). "
                              "Repeatable, and/or comma-separated in one use: "
                              "--disable-rule Embedded.Acronyms,Embedded.Spelling. "
                              "Does not touch .vale.ini.")
    args = parser.parse_args()
    disable_rules = [r.strip() for group in args.disable_rule for r in group.split(",") if r.strip()]

    files, _manifest_used = resolve_target_files(args.manifest)
    if not files:
        print("No entries found in manifest.", file=sys.stderr)
        return 0

    findings: list[Finding] = []
    if not args.no_structure:
        rules = load_structure_rules()
        for path in files:
            findings.extend(check_structure(path, rules))
        findings.extend(check_cross_file_anchors(files, rules))

    if not args.no_markdownlint:
        findings.extend(check_markdownlint(files, args.markdownlint_bin))
    if not args.no_vale:
        findings.extend(check_prose(files, args.vale_bin, args.requirements, disable_rules))

    if args.editor_format:
        write_editor_format(findings)
    else:
        print_report(findings, color=_use_color(args.no_color))
    if args.csv:
        write_csv(findings, args.csv)
    return 0  # always 0: warnings only, per project convention


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130) from None
