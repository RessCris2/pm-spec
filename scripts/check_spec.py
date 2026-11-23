#!/usr/bin/env python3
"""Check a spec written by the pm-spec skill against the code.

Usage:
  check_spec.py SPEC_DIR [--repo REPO] [--diff BASE] [--fix-lines] [--json OUT]

Without --diff: verifies every evidence link in SPEC_DIR/*.md (file exists,
line range inside the file, quote present in those lines), flags facts in
evidence sections that cite nothing, checks prototype and diagram rules, and
lists sentences that look duplicated (input for the reviewer).

With --diff BASE (a commit, branch or tag): compares the code at the merge
base of BASE and HEAD with the working tree and reports
  affected   evidence whose cited lines were changed or deleted
  moved      evidence whose lines only shifted (fixable with --fix-lines)
  renamed    evidence in a renamed file (fixed with --fix-lines)
  uncovered  changed code files that no evidence cites (possible new
             entities, states, rules or pages)
--fix-lines rewrites the line numbers of moved evidence and the paths of
renamed files in place. Affected evidence is never rewritten: a person or
the agent has to re-read the code.

Exit code 1 when there are errors.
"""
import argparse
import json
import os
import re
import subprocess
import sys

LINK = re.compile(r'(!?)\[([^\]]*)\]\(\s*<?([^)\s>]+)>?(?:\s+"((?:[^"\\]|\\.)*)")?\s*\)')
ANCHOR = re.compile(r'^L(\d+)(?:-L(\d+))?$')
SECTION = re.compile(r'<!--\s*spec:section\s+([\w-]+)\s*-->')
PROTOTYPE = re.compile(r'<!--\s*spec:prototype\s+id=([\w-]+)\s+status=(\w+)\s*-->')
UNKNOWN = ("〔未知〕", "[unknown]")
EVIDENCE_SECTIONS = {"overview", "entities", "relations", "lifecycles", "decisions",
                     "flows", "pages", "gaps"}
REQUIRED_SECTIONS = ["readers", "overview", "entities", "relations", "lifecycles",
                     "decisions", "flows", "pages", "gaps", "proposals", "open-questions"]
CODE_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".go", ".java", ".kt",
            ".rb", ".php", ".cs", ".rs", ".swift", ".sql", ".prisma", ".graphql", ".proto"}
LIST_ITEM = re.compile(r'^(\s*)(?:[-*+]|\d+[.)])\s+')


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=True).stdout


def repo_root(start):
    try:
        return git(start, "rev-parse", "--show-toplevel").strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def read_lines(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read().splitlines()


def norm(s):
    return " ".join(s.split())


class Spec:
    """All links, sections and markers of the Markdown files in a spec directory."""

    def __init__(self, spec_dir, repo):
        self.spec_dir, self.repo = spec_dir, repo
        self.files = sorted(os.path.join(dp, f) for dp, dn, fs in os.walk(spec_dir)
                            for f in fs if f.endswith(".md") and ".cache" not in dp)
        self.text = {p: read_lines(p) for p in self.files}
        self.evidence, self.assets, self.sections, self.prototypes = [], [], {}, []
        for md in self.files:
            self._parse(md)

    def resolve(self, md, target):
        """Repository-relative path for a link target, or None if it leaves the repo."""
        if target.startswith("/"):
            path = os.path.normpath(os.path.join(self.repo, target.lstrip("/")))
        else:
            path = os.path.normpath(os.path.join(os.path.dirname(md), target))
        rel = os.path.relpath(path, self.repo)
        return None if rel.startswith("..") else rel

    def _parse(self, md):
        section, fence = None, False
        for n, line in enumerate(self.text[md], 1):
            if line.lstrip().startswith(("```", "~~~")):
                fence = not fence
                continue
            if fence:
                continue
            m = SECTION.search(line)
            if m:
                section = m.group(1)
                self.sections.setdefault(section, (md, n))
            m = PROTOTYPE.search(line)
            if m:
                self.prototypes.append({"md": md, "line": n, "id": m.group(1), "status": m.group(2)})
            for m in LINK.finditer(line):
                bang, _, target, quote = m.groups()
                if quote:
                    quote = re.sub(r'\\(.)', r'\1', quote)
                if re.match(r'^[a-z]+:', target) or target.startswith("#"):
                    continue
                path, _, anchor = target.partition("#")
                rel = self.resolve(md, path)
                if rel is None:
                    continue
                item = {"md": md, "line": n, "raw": m.group(0), "target": path, "file": rel,
                        "anchor": anchor, "quote": quote, "section": section}
                in_spec = os.path.abspath(os.path.join(self.repo, rel)).startswith(
                    os.path.abspath(self.spec_dir) + os.sep)
                if bang or in_spec:
                    self.assets.append(item)
                else:
                    am = ANCHOR.match(anchor) if anchor else None
                    item["lines"] = [int(am.group(1)), int(am.group(2) or am.group(1))] if am else None
                    self.evidence.append(item)

    def lines_with_evidence(self):
        return {(e["md"], e["line"]) for e in self.evidence}


def check(spec, problems):
    cache = {}

    def src(rel):
        if rel not in cache:
            try:
                cache[rel] = read_lines(os.path.join(spec.repo, rel))
            except (OSError, IsADirectoryError):
                cache[rel] = None
        return cache[rel]

    where = lambda x: f"{os.path.relpath(x['md'], spec.spec_dir)}:{x['line']}"
    for e in spec.evidence:
        lines = src(e["file"])
        if lines is None:
            if not os.path.isdir(os.path.join(spec.repo, e["file"])):
                problems.append(("error", where(e), f"evidence file not found: {e['file']}"))
            continue
        if e["anchor"] and not e["lines"]:
            problems.append(("error", where(e), f"line anchor must be #L12 or #L12-L30: #{e['anchor']}"))
            continue
        if e["lines"]:
            a, b = e["lines"]
            if a < 1 or b < a or b > len(lines):
                problems.append(("error", where(e), f"lines {a}-{b} outside {e['file']} ({len(lines)} lines)"))
                continue
            if e["quote"] and norm(e["quote"]) not in norm("\n".join(lines[a - 1:b])):
                problems.append(("error", where(e), f"quote not found in {e['file']}:{a}-{b}: {e['quote'][:60]!r}"))
        elif e["quote"] and norm(e["quote"]) not in norm("\n".join(lines)):
            problems.append(("error", where(e), f"quote not found in {e['file']}: {e['quote'][:60]!r}"))

    for a in spec.assets:
        if not os.path.exists(os.path.join(spec.repo, a["file"])):
            hint = " (run render_diagrams.py)" if a["file"].endswith(".svg") else ""
            level = "warning" if a["file"].endswith(".svg") else "error"
            problems.append((level, where(a), f"linked file missing: {a['file']}{hint}"))

    for sid in REQUIRED_SECTIONS:
        if sid not in spec.sections:
            problems.append(("warning", "structure", f"section marker missing: <!-- spec:section {sid} -->"))

    # Facts in evidence sections: list items and table rows must cite code or say unknown.
    with_ev = spec.lines_with_evidence()
    for md in spec.files:
        section, fence, stack, table_ok, prev = None, False, [], None, ""
        for n, line in enumerate(spec.text[md], 1):
            if line.lstrip().startswith(("```", "~~~")):
                fence = not fence
            m = SECTION.search(line)
            if m:
                section = m.group(1)
            if fence or section not in EVIDENCE_SECTIONS:
                prev = line if line.strip() else prev
                continue
            cited = (md, n) in with_ev or any(u in line for u in UNKNOWN)
            if line.lstrip().startswith("|"):
                if table_ok is None:  # header row: the table is covered by a source line just above it
                    table_ok = any(x["md"] == md and x["line"] == n - 1 - k for x in spec.evidence
                                   for k in range(0, 2)) or (md, n) in with_ev
                    continue
                if re.match(r'^\s*\|[\s:|-]+\|\s*$', line):
                    continue
                if not (cited or table_ok):
                    problems.append(("warning", f"{os.path.relpath(md, spec.spec_dir)}:{n}",
                                     "table row cites no code; add a source link to the row or above the table, or mark 〔未知〕"))
                continue
            table_ok = None
            lm = LIST_ITEM.match(line)
            if lm:
                indent = len(lm.group(1))
                stack = [s for s in stack if s[0] < indent]
                parent_cited = any(s[1] for s in stack)
                if not (cited or parent_cited):
                    problems.append(("warning", f"{os.path.relpath(md, spec.spec_dir)}:{n}",
                                     "list item cites no code; add a source link or mark 〔未知〕"))
                stack.append((indent, cited or parent_cited))
            elif line.strip() and not line.startswith(" "):
                stack = []

    # Prototypes: an SVG only after the ASCII draft was confirmed.
    for p in spec.prototypes:
        svg = os.path.join(spec.spec_dir, "prototypes", p["id"] + ".svg")
        w = f"{os.path.relpath(p['md'], spec.spec_dir)}:{p['line']}"
        if p["status"] not in ("pending", "confirmed"):
            problems.append(("error", w, f"prototype status must be pending or confirmed: {p['status']}"))
        elif p["status"] == "pending" and os.path.exists(svg):
            problems.append(("error", w, f"prototype {p['id']} has an SVG but its ASCII draft is still pending"))
        elif p["status"] == "confirmed" and not os.path.exists(svg):
            problems.append(("warning", w, f"prototype {p['id']} is confirmed: draw prototypes/{p['id']}.svg"))

    diagrams = os.path.join(spec.spec_dir, "diagrams")
    if os.path.isdir(diagrams):
        for f in sorted(os.listdir(diagrams)):
            if f.endswith(".puml"):
                svg = os.path.join(diagrams, f[:-5] + ".svg")
                if not os.path.exists(svg) or os.path.getmtime(svg) < os.path.getmtime(os.path.join(diagrams, f)):
                    problems.append(("warning", f"diagrams/{f}", "SVG missing or older than source; run render_diagrams.py"))


def duplicates(spec, limit=30):
    """Pairs of sentences in different places that say nearly the same thing."""
    sents = []
    for md in spec.files:
        fence = False
        for n, line in enumerate(spec.text[md], 1):
            if line.lstrip().startswith(("```", "~~~")):
                fence = not fence
            if fence or line.lstrip().startswith(("|", "<!--", "!")):
                continue
            plain = LINK.sub(lambda m: m.group(2), line)
            plain = re.sub(r'[#>*`_〔〕\[\]]|^\s*(?:[-+]|\d+[.)])\s+', "", plain)
            for s in re.split(r'[。！？；!?;]|(?<=[a-z])\.\s', plain):
                s = s.strip()
                if len(s) >= 12:
                    grams = {s[i:i + 3] for i in range(len(s) - 2)}
                    sents.append((os.path.relpath(md, spec.spec_dir), n, s, grams))
    pairs = []
    for i in range(len(sents)):
        for j in range(i + 1, len(sents)):
            a, b = sents[i], sents[j]
            if (a[0], a[1]) == (b[0], b[1]) or min(len(a[2]), len(b[2])) / max(len(a[2]), len(b[2])) < 0.5:
                continue
            sim = len(a[3] & b[3]) / len(a[3] | b[3])
            if sim >= 0.6:
                pairs.append({"a": f"{a[0]}:{a[1]}", "b": f"{b[0]}:{b[1]}", "similarity": round(sim, 2),
                              "text_a": a[2][:80], "text_b": b[2][:80]})
    pairs.sort(key=lambda p: -p["similarity"])
    return pairs[:limit]


def parse_diff(text):
    """{old_path: {"new": new_path or None, "hunks": [(old_start, old_len, new_start, new_len)]}}"""
    files, cur = {}, None
    for line in text.splitlines():
        if line.startswith("diff --git "):
            m = re.match(r'diff --git a/(.*) b/(.*)$', line)
            cur = {"new": m.group(2), "hunks": []}
            files[m.group(1)] = cur
        elif cur is None:
            continue
        elif line.startswith("deleted file mode"):
            cur["new"] = None
        elif line.startswith("new file mode"):
            cur["added"] = True
        elif line.startswith("@@"):
            m = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            a, b, c, d = m.groups()
            cur["hunks"].append((int(a), int(b if b is not None else 1), int(c), int(d if d is not None else 1)))
    return files


def map_range(hunks, s, e):
    """('affected', None) if [s, e] was touched, else ('ok', (s2, e2)) after shifting."""
    delta = 0
    for a, b, c, d in hunks:
        if b > 0:
            end = a + b - 1
            if a <= e and end >= s:
                return "affected", None
            if end < s:
                delta += d - b
        else:  # pure insertion after old line a
            if s <= a < e:
                return "affected", None
            if a < s:
                delta += d
    return "ok", (s + delta, e + delta)


def diff_report(spec, base):
    mb = git(spec.repo, "merge-base", base, "HEAD").strip()
    files = parse_diff(git(spec.repo, "diff", "-U0", "--no-color", "-M", mb))
    for new in git(spec.repo, "ls-files", "--others", "--exclude-standard").splitlines():
        files.setdefault(new, {"new": new, "hunks": [], "added": True})  # untracked files are additions
    spec_rel = os.path.relpath(spec.spec_dir, spec.repo)
    out = {"base": mb, "affected": [], "moved": [], "renamed": [], "uncovered": []}
    cited = set()
    for e in spec.evidence:
        cited.add(e["file"])
        f = files.get(e["file"])
        if not f:
            continue
        ref = {"md": os.path.relpath(e["md"], spec.spec_dir), "line": e["line"], "section": e["section"],
               "file": e["file"], "lines": e["lines"]}
        if f["new"] is None:
            out["affected"].append({**ref, "reason": "file deleted"})
            continue
        if f["new"] != e["file"]:
            out["renamed"].append({**ref, "to": f["new"]})
        if not e["lines"]:
            if f["hunks"]:
                out["affected"].append({**ref, "reason": "file changed (evidence cites the whole file)"})
            continue
        status, new = map_range(f["hunks"], *e["lines"])
        if status == "affected":
            out["affected"].append({**ref, "reason": "cited lines changed"})
        elif new != tuple(e["lines"]):
            out["moved"].append({**ref, "to_lines": list(new)})
    for old, f in files.items():
        path = f["new"] or old
        if (os.path.splitext(path)[1] in CODE_EXT and old not in cited and path not in cited
                and not path.startswith(spec_rel + "/")):
            out["uncovered"].append({"file": path, "status": "deleted" if f["new"] is None else
                                     "added" if f.get("added") else "modified"})
    return out


def fix_lines(spec, report):
    edits = {}
    for kind in ("moved", "renamed"):
        for r in report[kind]:
            edits.setdefault((r["md"], r["line"], r["file"], tuple(r["lines"] or ())), {}).update(
                {"lines": r.get("to_lines"), "file": r.get("to")})
    changed = 0
    for e in spec.evidence:
        key = (os.path.relpath(e["md"], spec.spec_dir), e["line"], e["file"], tuple(e["lines"] or ()))
        if key not in edits:
            continue
        ed = edits[key]
        target = e["target"]
        if ed.get("file"):
            target = "/" + ed["file"] if e["target"].startswith("/") else os.path.relpath(
                os.path.join(spec.repo, ed["file"]), os.path.dirname(e["md"]))
        lines = ed.get("lines") or e["lines"]
        anchor = (f"#L{lines[0]}" + (f"-L{lines[1]}" if lines[1] != lines[0] else "")) if lines else ""
        new = e["raw"].replace(e["target"] + ("#" + e["anchor"] if e["anchor"] else ""), target + anchor, 1)
        row = spec.text[e["md"]][e["line"] - 1]
        spec.text[e["md"]][e["line"] - 1] = row.replace(e["raw"], new, 1)
        changed += 1
    for md, lines in spec.text.items():
        with open(md, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    return changed


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("spec_dir")
    ap.add_argument("--repo", help="repository root (default: the git repository containing SPEC_DIR)")
    ap.add_argument("--diff", metavar="BASE")
    ap.add_argument("--fix-lines", action="store_true")
    ap.add_argument("--json", metavar="OUT", help="also write the full report as JSON")
    args = ap.parse_args()
    spec_dir = os.path.abspath(args.spec_dir)
    repo = os.path.abspath(args.repo) if args.repo else repo_root(spec_dir)
    if not repo:
        sys.exit("cannot find the repository root; pass --repo")
    spec = Spec(spec_dir, repo)
    if not spec.files:
        sys.exit(f"no Markdown files in {spec_dir}")

    report = {"evidence": len(spec.evidence)}
    if args.diff:
        report["diff"] = diff_report(spec, args.diff)
        if args.fix_lines:
            n = fix_lines(spec, report["diff"])
            print(f"fixed {n} evidence links (moved lines / renamed files)")
            spec = Spec(spec_dir, repo)
    problems = []
    check(spec, problems)
    report["errors"] = [{"where": w, "message": m} for lv, w, m in problems if lv == "error"]
    report["warnings"] = [{"where": w, "message": m} for lv, w, m in problems if lv == "warning"]
    report["duplicates"] = duplicates(spec)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=1)

    print(f"spec: {len(spec.files)} files, {len(spec.evidence)} evidence links, "
          f"{len(spec.prototypes)} prototypes, sections: {', '.join(spec.sections) or 'none'}")
    if args.diff:
        d = report["diff"]
        print(f"diff vs {d['base'][:10]}: {len(d['affected'])} affected, {len(d['moved'])} moved, "
              f"{len(d['renamed'])} renamed, {len(d['uncovered'])} uncovered changed files")
        for r in d["affected"]:
            print(f"  AFFECTED  {r['md']}:{r['line']} [{r['section']}] {r['file']}"
                  f"{':%d-%d' % tuple(r['lines']) if r['lines'] else ''} ({r['reason']})")
        for r in d["uncovered"][:40]:
            print(f"  UNCOVERED {r['file']} ({r['status']})")
    for p in report["duplicates"]:
        print(f"  DUPLICATE? {p['a']} ~ {p['b']} ({p['similarity']}): {p['text_a']!r}")
    for x in report["errors"]:
        print(f"ERROR   {x['where']}: {x['message']}")
    for x in report["warnings"]:
        print(f"warning {x['where']}: {x['message']}")
    print(f"{len(report['errors'])} errors, {len(report['warnings'])} warnings, "
          f"{len(report['duplicates'])} possible duplicates")
    sys.exit(1 if report["errors"] else 0)


if __name__ == "__main__":
    main()
