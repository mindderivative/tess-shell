#!/usr/bin/env python3
"""Export the design vault into docs/ for GitHub.

The vault is an Obsidian vault (the source of truth, kept as it is). GitHub cannot render
wikilinks, note embeds, Dataview blocks or most Obsidian callout types, so this tool writes a
converted copy of the committed notes into docs/ of this repository.

What it does, from the vault's committed state (git HEAD, or --rev):

* copies every tracked file except the vault's own .gitignore;
* turns [[wikilinks]] into relative Markdown links with GitHub heading anchors;
* expands note and section embeds (![[Note#Heading]]) in place;
* maps Obsidian callouts to GitHub alerts (NOTE, TIP, IMPORTANT, WARNING, CAUTION);
* replaces Dataview blocks and Bases embeds with a short note;
* drops the related and depends_on front matter keys (their links are in each note's body);
* replaces /home/phil with ~ in every file;
* writes docs/README.md and docs/.sync.json (the provenance of the copy).

It writes only inside <clone>/docs/. It never commits, pushes or touches the vault. Files it wrote
earlier and the vault no longer has are removed; with --prune every other file under docs/ that
the vault does not have is removed too.

Usage:
    python3 -I tools/sync_docs.py --vault "~/Projects/Obsidian/Tesserae Shell"
    python3 -I tools/sync_docs.py --vault ... --out /tmp/check      # write to /tmp/check/docs
    python3 -I tools/sync_docs.py --vault ... --dry-run             # report only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
from collections import defaultdict
from pathlib import Path

LOCAL_HOME = "/home/phil"
SKIP_FILES = {".gitignore"}
DROP_KEYS = {"related", "depends_on"}
MAX_EMBED_DEPTH = 3

ALERTS = {
    "summary": "NOTE", "abstract": "NOTE", "tldr": "NOTE", "info": "NOTE", "note": "NOTE",
    "question": "NOTE", "help": "NOTE", "faq": "NOTE", "example": "NOTE", "quote": "NOTE",
    "cite": "NOTE", "todo": "NOTE",
    "tip": "TIP", "hint": "TIP", "success": "TIP", "check": "TIP", "done": "TIP",
    "important": "IMPORTANT",
    "warning": "WARNING", "caution": "WARNING", "attention": "WARNING",
    "danger": "CAUTION", "error": "CAUTION", "failure": "CAUTION", "fail": "CAUTION",
    "missing": "CAUTION", "bug": "CAUTION",
}

FENCE = re.compile(r"^(\s*)(`{3,}|~{3,})\s*(.*)$")
HEADING = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")
CALLOUT = re.compile(r"^(\s*)>\s*\[!([A-Za-z-]+)\][+-]?[ \t]*(.*)$")
OWN_LINE_EMBED = re.compile(r"^\s*!\[\[([^\]]+)\]\]\s*$")
SLUG_DROP = re.compile(r"[^\w\- ]", re.UNICODE)


def git(vault: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(vault), *args], check=True, capture_output=True).stdout


def slug(text: str) -> str:
    """GitHub's heading anchor: lower case, drop punctuation, spaces to hyphens."""
    return SLUG_DROP.sub("", text.strip().lower()).replace(" ", "-")


def split_front_matter(text: str) -> tuple[str, str]:
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[: end + 5], text[end + 5 :]
    return "", text


def parse_aliases(front: str) -> list[str]:
    out: list[str] = []
    m = re.search(r"^aliases:\s*\[(.*?)\]\s*$", front, re.M)
    if m:
        out += [x.strip().strip("\"'") for x in m.group(1).split(",") if x.strip()]
    m = re.search(r"^aliases:\s*\n((?:[ \t]+-[ \t]+.*\n?)+)", front, re.M)
    if m:
        out += [x.strip().strip("\"'") for x in re.findall(r"^[ \t]+-[ \t]+(.*)$", m.group(1), re.M)]
    return out


def drop_front_matter_keys(front: str) -> str:
    lines = front.split("\n")
    out: list[str] = []
    skipping = False
    for line in lines:
        key = re.match(r"^([A-Za-z_][\w-]*):", line)
        if key:
            skipping = key.group(1) in DROP_KEYS
        elif skipping and not (line.startswith((" ", "\t", "- ")) or line.strip() == ""):
            skipping = False
        if not skipping:
            out.append(line)
    return "\n".join(out)


class Vault:
    def __init__(self, vault: Path, rev: str) -> None:
        self.vault, self.rev = vault, rev
        names = git(vault, "ls-tree", "-r", "--name-only", "-z", rev).decode("utf8").split("\0")
        self.paths = sorted(p for p in names if p and Path(p).name not in SKIP_FILES)
        self.blobs: dict[str, bytes] = {p: git(vault, "show", f"{rev}:{p}") for p in self.paths}
        self.warnings: list[str] = []
        self.stats: defaultdict[str, int] = defaultdict(int)
        self.fronts: dict[str, str] = {}
        self.bodies: dict[str, str] = {}
        for p in self.paths:
            if p.endswith(".md"):
                front, body = split_front_matter(self.blobs[p].decode("utf8"))
                self.fronts[p], self.bodies[p] = front, body
        self._build_name_index()
        self.expanded: dict[str, str] = {}
        self.heads: dict[str, dict[str, str]] = {}

    def warn(self, msg: str) -> None:
        if msg not in self.warnings:
            self.warnings.append(msg)

    def _build_name_index(self) -> None:
        self.by_name: dict[str, str] = {}
        self.by_file: dict[str, str] = {}
        for p in self.paths:
            self.by_file[Path(p).name.lower()] = p
            if p.endswith(".md"):
                self.by_name[Path(p).stem.lower()] = p
        for p in self.paths:
            if not p.endswith(".md"):
                continue
            for alias in parse_aliases(self.fronts[p]):
                key = alias.lower()
                if key in self.by_name and self.by_name[key] != p:
                    if Path(self.by_name[key]).stem.lower() != key:
                        self.warn(f"alias '{alias}' is shared by {self.by_name[key]} and {p}; the first wins")
                    continue
                self.by_name[key] = p

    def resolve(self, name: str) -> str | None:
        key = name.strip().lower()
        if not key:
            return None
        if key in self.by_name:
            return self.by_name[key]
        if key.endswith(".md") and key[:-3] in self.by_name:
            return self.by_name[key[:-3]]
        return self.by_file.get(key)

    # ---- headings -------------------------------------------------------------------------

    def link_display(self, inner: str) -> str:
        left, _, alias = inner.partition("|")
        if alias.strip():
            return alias.strip()
        name, _, frag = left.partition("#")
        name, frag = name.strip(), frag.strip()
        return f"{name} > {frag}" if name and frag else (name or frag)

    def plain_heading(self, text: str) -> str:
        text = re.sub(r"\[\[([^\]]+)\]\]", lambda m: self.link_display(m.group(1)), text)
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
        return text.replace("**", "").replace("*", "")

    def headings_of(self, text: str) -> list[tuple[int, str, int]]:
        """(level, plain text, line index) of every heading outside code fences."""
        out, fence = [], None
        for i, line in enumerate(text.split("\n")):
            m = FENCE.match(line)
            if m:
                marker = m.group(2)
                if fence is None:
                    fence = marker[0] * len(marker)
                elif marker.startswith(fence[0]) and len(marker) >= len(fence) and not m.group(3):
                    fence = None
                continue
            if fence is None:
                h = HEADING.match(line)
                if h:
                    out.append((len(h.group(1)), self.plain_heading(h.group(2)), i))
        return out

    # ---- pass 1: embeds -------------------------------------------------------------------

    @staticmethod
    def qualify(lines: list[str], stem: str) -> list[str]:
        """[[#Heading]] inside embedded text refers to the source note, so name it."""
        out, fence = [], None
        for line in lines:
            m = FENCE.match(line)
            if m:
                marker = m.group(2)
                if fence is None:
                    fence = marker[0] * len(marker)
                elif marker.startswith(fence[0]) and len(marker) >= len(fence) and not m.group(3):
                    fence = None
                out.append(line)
                continue
            if fence is None and "[[#" in line:
                parts = line.split("`")
                for i in range(0, len(parts), 2):
                    parts[i] = parts[i].replace("[[#", f"[[{stem}#")
                line = "`".join(parts)
            if fence is None and "](#" in line:
                parts = line.split("`")
                for i in range(0, len(parts), 2):
                    parts[i] = re.sub(r"\]\(#([^)\s]+)\)", lambda m: f"](tess-note:{stem}#{m.group(1)})", parts[i])
                line = "`".join(parts)
            out.append(line)
        return out

    def section(self, path: str, frag: str, depth: int) -> list[str] | None:
        text = self.bodies[path]
        lines = self.qualify(text.split("\n"), Path(path).stem)
        if not frag:
            return self.expand_lines(lines, depth + 1)
        target = slug(self.plain_heading(frag))
        heads = self.headings_of(text)
        for n, (level, plain, idx) in enumerate(heads):
            if slug(plain) == target:
                end = len(lines)
                for lvl2, _, idx2 in heads[n + 1 :]:
                    if lvl2 <= level:
                        end = idx2
                        break
                return self.expand_lines(lines[idx + 1 : end], depth + 1)
        return None

    def expand_lines(self, lines: list[str], depth: int) -> list[str]:
        out, fence = [], None
        for line in lines:
            m = FENCE.match(line)
            if m:
                marker = m.group(2)
                if fence is None:
                    fence = marker[0] * len(marker)
                elif marker.startswith(fence[0]) and len(marker) >= len(fence) and not m.group(3):
                    fence = None
                out.append(line)
                continue
            e = OWN_LINE_EMBED.match(line) if fence is None else None
            if not e:
                out.append(line)
                continue
            target, _, alias = e.group(1).partition("|")
            name, _, frag = target.partition("#")
            path = self.resolve(name)
            self.stats["embeds"] += 1
            if path is None:
                self.warn(f"embed target not found: {target}")
                out.append(f"> [!NOTE]\n> Embedded content not found: {target}")
            elif not path.endswith(".md"):
                out += [
                    "> [!NOTE]",
                    f"> This is an Obsidian view of `{Path(path).name}`"
                    + (f" (section {frag.strip()})" if frag.strip() else "")
                    + " and is not shown on GitHub.",
                ]
            elif depth >= MAX_EMBED_DEPTH:
                out.append(f"> [!NOTE]\n> Embedding stopped here ({target}).")
            else:
                got = self.section(path, frag.strip(), depth)
                if got is None:
                    self.warn(f"embedded heading not found: {target}")
                    out.append(f"> [!NOTE]\n> Embedded section not found: {target}")
                else:
                    out += got
        return out

    # ---- pass 2/3: links and callouts -----------------------------------------------------

    def rel(self, cur: str, target: str) -> str:
        r = os.path.relpath(target, os.path.dirname(cur) or ".")
        return urllib.parse.quote(r.replace(os.sep, "/"), safe="/")

    def convert_link(self, inner: str, cur: str, embed: bool) -> str:
        left, _, _alias = inner.partition("|")
        name, _, frag = left.partition("#")
        display = self.link_display(inner)
        target = cur if not name.strip() else self.resolve(name)
        if target is None:
            self.warn(f"{cur}: link target not found: [[{inner}]]")
            self.stats["links unresolved"] += 1
            return display
        href = "" if target == cur else self.rel(cur, target)
        frag = frag.strip()
        if frag and not frag.startswith("^") and target.endswith(".md"):
            s = slug(self.plain_heading(frag))
            if s in self.heads.get(target, {}):
                href += "#" + s
            else:
                self.warn(f"{cur}: heading not found in {target}: [[{inner}]]")
                self.stats["anchors unresolved"] += 1
        if href in ("", "#"):
            return display
        self.stats["links converted"] += 1
        return f"[{display}]({href})"

    def convert_inline(self, line: str, cur: str) -> str:
        """Convert wikilinks outside inline code spans on one line."""
        out, i, n = [], 0, len(line)
        while i < n:
            c = line[i]
            if c == "`":
                j = i
                while j < n and line[j] == "`":
                    j += 1
                run = line[i:j]
                k = line.find(run, j)
                while k != -1 and (k + len(run) < n and line[k + len(run)] == "`"):
                    k = line.find(run, k + len(run) + 1)
                if k == -1:
                    out.append(run)
                    i = j
                else:
                    out.append(line[i : k + len(run)])
                    i = k + len(run)
            elif line.startswith("](tess-note:", i) and line.find(")", i) != -1:
                end = line.find(")", i)
                stem, _, frag = line[i + len("](tess-note:") : end].partition("#")
                target = self.resolve(stem)
                if target is None or target == cur:
                    out.append(f"](#{frag})")
                else:
                    out.append(f"]({self.rel(cur, target)}#{frag})")
                i = end + 1
            elif line.startswith("[[", i) or line.startswith("![[", i):
                embed = line.startswith("!")
                start = i + (3 if embed else 2)
                end = line.find("]]", start)
                if end == -1:
                    out.append(line[i : i + 2])
                    i += 2
                else:
                    out.append(self.convert_link(line[start:end], cur, embed))
                    i = end + 2
            else:
                out.append(c)
                i += 1
        return "".join(out)

    def needs_verification_list(self, cur: str) -> str:
        """The static version of the vault's Dataview list of notes tagged needs-verification."""
        items = []
        for p, body in self.bodies.items():
            stem = Path(p).stem
            front = self.fronts[p]
            if stem in ("Open Questions", "AGENTS") or re.search(r"^status:\s*superseded\s*$", front, re.M):
                continue
            tagged = re.search(r"^tags:.*needs-verification", front, re.M) is not None
            if not tagged:
                m = re.search(r"^tags:\s*\n((?:[ \t]+-[ \t]+.*\n?)+)", front, re.M)
                tagged = bool(m and "needs-verification" in m.group(1))
            if not tagged:
                bare = re.sub(r"`[^`\n]*`", "", re.sub(r"```.*?```", "", body, flags=re.S))
                tagged = re.search(r"(?<![\w/#])#needs-verification\b", bare) is not None
            if tagged:
                items.append((stem.lower(), f"- [{stem}]({self.rel(cur, p)})"))
        return "\n".join(line for _k, line in sorted(items))

    def convert_text(self, text: str, cur: str) -> str:
        out, fence = [], None
        skipped: list[str] = []
        skip_js = False
        lines = text.split("\n")
        for line in lines:
            m = FENCE.match(line)
            if m:
                marker, info = m.group(2), m.group(3)
                if fence is None:
                    if info.lower().startswith("dataview"):
                        self.stats["dataview blocks replaced"] += 1
                        skipped = []
                        skip_js = info.lower().startswith("dataviewjs")
                        fence = ("skip", marker[0] * len(marker))
                        continue
                    fence = ("keep", marker[0] * len(marker))
                    out.append(line)
                    continue
                kind, mark = fence
                if marker.startswith(mark[0]) and len(marker) >= len(mark) and not info:
                    fence = None
                    if kind == "keep":
                        out.append(line)
                    else:
                        query = "\n".join(skipped)
                        if not skip_js and "needs-verification" in query and query.lstrip().startswith("LIST"):
                            self.stats["dataview lists generated"] += 1
                            out.append(self.needs_verification_list(cur))
                        else:
                            out.append("> [!NOTE]\n> An Obsidian Dataview query is here; it is not shown on GitHub.")
                    continue
            if fence is not None:
                if fence[0] == "keep":
                    out.append(line)
                else:
                    skipped.append(line)
                continue
            c = CALLOUT.match(line)
            if c:
                indent, kind, title = c.groups()
                alert = ALERTS.get(kind.lower())
                if alert is None:
                    self.warn(f"{cur}: unknown callout type '{kind}', shown as NOTE")
                    alert = "NOTE"
                self.stats["callouts mapped"] += 1
                out.append(f"{indent}> [!{alert}]")
                if title.strip():
                    out.append(f"{indent}> **{self.convert_inline(title.strip(), cur)}**")
                continue
            out.append(self.convert_inline(line, cur))
        return "\n".join(out)

    # ---- the whole export -----------------------------------------------------------------

    def build(self) -> dict[str, bytes]:
        for p, body in self.bodies.items():
            self.expanded[p] = "\n".join(self.expand_lines(body.split("\n"), 0))
        for p, body in self.expanded.items():
            seen: defaultdict[str, int] = defaultdict(int)
            heads: dict[str, str] = {}
            for _level, plain, _i in self.headings_of(body):
                s = slug(plain)
                n = seen[s]
                seen[s] += 1
                heads.setdefault(s if n == 0 else f"{s}-{n}", plain)
            self.heads[p] = heads
        out: dict[str, bytes] = {}
        for p in self.paths:
            if p.endswith(".md"):
                front = drop_front_matter_keys(self.fronts[p]) if self.fronts[p] else ""
                body = self.convert_text(self.expanded[p], p)
                text = front + body
            else:
                text = self.blobs[p].decode("utf8", errors="replace")
            if LOCAL_HOME in text:
                self.stats["local paths replaced"] += text.count(LOCAL_HOME)
                text = text.replace(LOCAL_HOME, "~")
            out[p] = text.encode("utf8")
        out["README.md"] = self.readme().encode("utf8")
        return out

    def readme(self) -> str:
        folders = sorted({p.split("/")[0] for p in self.paths if "/" in p})
        rows = []
        for f in folders:
            idx = next((c for c in (f"{f}/{f}.md", f"{f}/Home.md", f"{f}/Index.md") if c in self.bodies), None)
            link = f"[{f}]({urllib.parse.quote(idx)})" if idx else f
            rows.append(f"- {link}")
        home = "00 Home/Home.md"
        return (
            "# Tesserae Shell design documentation\n\n"
            "> [!NOTE]\n"
            "> This folder is generated from the design vault (an Obsidian vault) by `tools/sync_docs.py`. "
            "Edit the notes in the vault. Changes made here are overwritten the next time the tool runs.\n\n"
            f"Start at [Home]({urllib.parse.quote(home)}) for the current status. Folders:\n\n"
            + "\n".join(rows)
            + "\n"
        )


def check_output(files: dict[str, bytes]) -> list[str]:
    """Verify relative links and anchors in the exported Markdown, and leftover Obsidian syntax."""
    problems: list[str] = []
    slugs: dict[str, set[str]] = {}
    for p, data in files.items():
        if not p.endswith(".md"):
            continue
        seen: defaultdict[str, int] = defaultdict(int)
        found: set[str] = set()
        fence = None
        for line in data.decode("utf8").split("\n"):
            m = FENCE.match(line)
            if m:
                marker = m.group(2)
                if fence is None:
                    fence = marker[0] * len(marker)
                elif marker.startswith(fence[0]) and len(marker) >= len(fence) and not m.group(3):
                    fence = None
                continue
            if fence is None:
                h = HEADING.match(line)
                if h:
                    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", h.group(2)).replace("**", "").replace("*", "")
                    s = slug(text)
                    n = seen[s]
                    seen[s] += 1
                    found.add(s if n == 0 else f"{s}-{n}")
        slugs[p] = found
    for p, data in files.items():
        if not p.endswith(".md"):
            continue
        fence = None
        for ln, line in enumerate(data.decode("utf8").split("\n"), 1):
            m = FENCE.match(line)
            if m:
                marker = m.group(2)
                if fence is None:
                    fence = marker[0] * len(marker)
                elif marker.startswith(fence[0]) and len(marker) >= len(fence) and not m.group(3):
                    fence = None
                continue
            if fence is not None:
                continue
            bare = re.sub(r"`[^`]*`", "", line)
            if "[[" in bare:
                problems.append(f"{p}:{ln}: wikilink left: {bare.strip()[:80]}")
            for dest in re.findall(r"\]\(([^)\s]+)\)", bare):
                if re.match(r"^[a-z]+:", dest):
                    continue
                path, _, frag = dest.partition("#")
                target = p if not path else os.path.normpath(os.path.join(os.path.dirname(p), urllib.parse.unquote(path)))
                if target not in files:
                    problems.append(f"{p}:{ln}: no file {target}")
                elif frag and target.endswith(".md") and frag not in slugs[target]:
                    problems.append(f"{p}:{ln}: no anchor #{frag} in {target}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault", required=True, help="the vault's git repository")
    ap.add_argument("--clone", default=str(Path(__file__).resolve().parents[1]), help="this repository (default: the parent of tools/)")
    ap.add_argument("--out", help="write <out>/docs instead of <clone>/docs (for testing)")
    ap.add_argument("--rev", default="HEAD", help="vault revision to export (default HEAD)")
    ap.add_argument("--dry-run", action="store_true", help="report, write nothing")
    ap.add_argument("--prune", action="store_true", help="also remove files under docs/ that the vault does not have")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--brief", action="store_true", help="print one summary line and any output problems (for the hook's log)")
    args = ap.parse_args()

    vault = Path(args.vault).expanduser().resolve()
    root = Path(args.out).expanduser().resolve() if args.out else Path(args.clone).expanduser().resolve()
    docs = root / "docs"
    v = Vault(vault, args.rev)
    files = v.build()
    problems = check_output(files)
    commit = git(vault, "rev-parse", args.rev).decode().strip()
    manifest = {
        "vault_commit": commit,
        "vault_subject": git(vault, "log", "-1", "--format=%s", args.rev).decode().strip(),
        "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "files": {p: hashlib.sha256(d).hexdigest()[:16] for p, d in sorted(files.items())},
    }
    mpath = docs / ".sync.json"
    previous: set[str] = set()
    if mpath.exists():
        try:
            previous = set(json.loads(mpath.read_text(encoding="utf8")).get("files", {}))
        except (ValueError, OSError):
            previous = set()
    written = unchanged = removed = 0
    if not args.dry_run:
        for p, data in files.items():
            dest = docs / p
            if dest.exists() and dest.read_bytes() == data:
                unchanged += 1
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            written += 1
        stale = previous - set(files)
        if args.prune and docs.exists():
            stale |= {str(f.relative_to(docs)) for f in docs.rglob("*") if f.is_file()} - set(files) - {".sync.json"}
        for p in sorted(stale):
            f = docs / p
            if f.is_file() and docs in f.resolve().parents:
                f.unlink()
                removed += 1
        for d in sorted((x for x in docs.rglob("*") if x.is_dir()), reverse=True):
            if not any(d.iterdir()):
                d.rmdir()
        new_manifest = json.dumps(manifest, indent=1, ensure_ascii=False) + "\n"
        if not mpath.exists() or json.loads(mpath.read_text(encoding="utf8")).get("files") != manifest["files"]:
            mpath.write_text(new_manifest, encoding="utf8")
    if args.brief:
        print(
            f"vault {commit[:7]}: {len(files)} files, {written} written, {removed} removed, "
            f"{v.stats.get('links unresolved', 0)} links left as text, {len(problems)} output problem(s)"
        )
        for pr in problems[:20]:
            print("  -", pr)
    elif not args.quiet:
        print(f"vault {commit[:7]} ({manifest['vault_subject']})")
        print(f"files: {len(files)}; written {written}, unchanged {unchanged}, removed {removed}" + (" (dry run)" if args.dry_run else ""))
        print("conversions:", dict(sorted(v.stats.items())))
        if v.warnings:
            print(f"warnings ({len(v.warnings)}):")
            for w in v.warnings:
                print("  -", w)
        print(f"output check: {len(problems)} problem(s)")
        for pr in problems[:40]:
            print("  -", pr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
