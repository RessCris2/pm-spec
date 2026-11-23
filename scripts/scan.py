#!/usr/bin/env python3
"""Find where a codebase defines its entities, states, rules, pages and entry points.

Usage: scan.py REPO [--out FILE] [--include GLOB ...] [--exclude GLOB ...]

Static and read-only: files are read as text and matched with patterns for
common frameworks (SQLAlchemy, Django, Prisma, TypeORM, Sequelize, Mongoose,
JPA, GORM, ActiveRecord, SQL migrations, Pydantic/dataclasses, TS types;
Next.js, React Router, Vue Router, SvelteKit, Angular; FastAPI, Flask,
Express, NestJS, Spring, Gin, Rails). The result is a map of where to start
reading, not a description: every hit is a candidate with file and line.

Kinds: entity (persisted models and tables), schema (API/DTO shapes, often
many; read them for field meaning, not as entities), state, rule, page, entry.
Writes JSON (default ./spec-candidates.json) and prints a summary by kind.
"""
import argparse
import fnmatch
import json
import os
import re
import subprocess
from collections import Counter, defaultdict

SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", ".next", ".nuxt", "out", "target",
             "__pycache__", ".venv", "venv", "env", ".tox", "coverage", ".cache", "site-packages"}
SECRET = re.compile(r'(^|/)(\.env(\..*)?|.*\.pem|.*\.key|id_rsa.*|.*secret.*|.*credential.*)$', re.I)
TEST = re.compile(r'(^|/)(tests?|__tests__|spec|e2e|cypress|fixtures?)/|(\.|_)(test|spec)\.[a-z]+$|(^|/)test_[^/]*$', re.I)
MAX_BYTES = 400_000

# kind -> list of (label, extensions, regex). Group 1, when present, is the name.
P = {
    "entity": [
        ("SQLAlchemy model", {".py"}, r'^class\s+(\w+)\s*\([^)]*\b(?:Base|DeclarativeBase|db\.Model|SQLModel)\b'),
        ("Django model", {".py"}, r'^class\s+(\w+)\s*\([^)]*\bmodels\.Model\b'),
        ("Prisma model", {".prisma"}, r'^model\s+(\w+)\s*\{'),
        ("TypeORM/JPA entity", {".ts", ".java", ".kt"}, r'@Entity\b'),
        ("Sequelize model", {".js", ".ts"}, r'\.define\(\s*[\'"](\w+)[\'"]'),
        ("Mongoose schema", {".js", ".ts"}, r'new\s+(?:mongoose\.)?Schema\s*\('),
        ("GORM model", {".go"}, r'^type\s+(\w+)\s+struct\s*\{'),
        ("ActiveRecord model", {".rb"}, r'^class\s+(\w+)\s*<\s*(?:ApplicationRecord|ActiveRecord::Base)'),
        ("SQL table", {".sql", ".py"}, r'(?i)create\s+table\s+(?:if\s+not\s+exists\s+)?["`]?(\w+)'),
        ("Alembic table", {".py"}, r'op\.create_table\(\s*[\'"](\w+)'),
    ],
    "schema": [
        ("Pydantic schema", {".py"}, r'^class\s+(\w+)\s*\([^)]*\bBaseModel\b'),
        ("TS interface/type", {".ts", ".tsx"}, r'^export\s+(?:interface|type)\s+([A-Z]\w+)\b'),
    ],
    "state": [
        ("status/state field", None, r'\b(\w*(?:status|state|stage|phase|lifecycle)\w*)\s*(?::\s*Mapped\[[^\]]*\]\s*=\s*)?[:=]?\s*(?:\w+\.)?(?:Column|Field|mapped_column|models\.\w+Field|@Column|Enum|\w*[Ee]num)\b'),
        ("enum", {".py"}, r'^class\s+(\w+)\s*\([^)]*\b(?:Enum|StrEnum|IntEnum|TextChoices|IntegerChoices)\b'),
        ("enum", {".ts", ".tsx", ".java", ".kt", ".prisma", ".cs"}, r'^\s*(?:export\s+)?enum\s+(\w+)'),
        ("state machine", None, r'\b(createMachine|xstate|django_fsm|FSMField|aasm|transitions\.Machine|@transition|state_machine)\b'),
        ("transition", None, r'\.(?:status|state)\s*=\s*([\w.\'"]+)'),
        ("soft delete / timestamps", None, r'\b(deleted_at|deletedAt|archived_at|cancelled_at|canceled_at|completed_at|published_at|expires_at|expired_at)\b'),
        ("scheduled job", None, r'\b(@scheduled|@Scheduled|cron\(|crontab|apscheduler|celery\.task|@shared_task|setInterval\(|schedule\.every)\b'),
    ],
    "rule": [
        ("permission", None, r'\b(permission\w*|require_role|has_role|is_admin|is_staff|@login_required|@roles_allowed|PreAuthorize|authorize|can\(\s*[\'"]|Depends\(\s*(?:get_current\w*|require\w*))\b'),
        ("validation", None, r'\b(@validator|@field_validator|@model_validator|validates\b|Joi\.|z\.object|yup\.|class-validator|@IsNotEmpty|@Min\(|@Max\(|ValidationError)\b'),
        ("limit/constant", None, r'^\s*(?:export\s+)?(?:const\s+)?([A-Z][A-Z0-9_]*(?:LIMIT|MAX|MIN|TIMEOUT|TTL|THRESHOLD|QUOTA|DAYS|HOURS|MINUTES|RETRIES|SIZE)\w*)\s*[:=]'),
        ("feature flag", None, r'\b(feature_flag\w*|featureFlag\w*|is_enabled\(|isEnabled\(|FEATURE_\w+|flags?\.\w+)\b'),
    ],
    "page": [
        ("Next.js page", None, r'__FILE__(?:^|/)(?:pages/(?!api/).+\.(?:tsx|jsx|js|ts)|app/(?:.+/)?page\.(?:tsx|jsx|js|ts))$'),
        ("SvelteKit page", None, r'__FILE__(?:^|/)routes/(?:.+/)?\+page\.svelte$'),
        ("Nuxt page", None, r'__FILE__(?:^|/)pages/.+\.vue$'),
        ("route path", {".ts", ".tsx", ".js", ".jsx", ".vue"}, r'''(?:<Route\b[^>]*\bpath=|\bpath\s*:)\s*[{]?\s*[`'"]([^`'"]+)[`'"]'''),
        ("template", {".html", ".jinja", ".jinja2", ".erb", ".hbs"}, r'__FILE__(?:^|/)(?:templates|views)/.+'),
    ],
    "entry": [
        ("HTTP route", {".py"}, r'@\w+\.(get|post|put|patch|delete|route|api_route|websocket)\(\s*[\'"]([^\'"]*)'),
        ("HTTP route", {".js", ".ts"}, r'\b(?:router|app|server)\.(get|post|put|patch|delete|all)\(\s*[`\'"]([^`\'"]+)'),
        ("HTTP route", {".ts"}, r'@(Get|Post|Put|Patch|Delete)\(\s*[\'"]?([^\'")]*)'),
        ("HTTP route", {".java", ".kt"}, r'@(Get|Post|Put|Patch|Delete|Request)Mapping\(\s*(?:value\s*=\s*)?"?([^")]*)'),
        ("HTTP route", {".go"}, r'\.(GET|POST|PUT|PATCH|DELETE|HandleFunc)\(\s*"([^"]+)"'),
        ("CLI command", {".py"}, r'@(?:click\.command|app\.command|\w+\.command)\b|add_parser\(\s*[\'"](\w+)'),
        ("queue consumer", None, r'\b(@consumer|@listener|@KafkaListener|@RabbitListener|subscribe\(|\.on\(\s*[\'"]message|consume\()'),
    ],
}


def list_files(repo):
    try:
        out = subprocess.run(["git", "-C", repo, "ls-files", "-co", "--exclude-standard"],
                             capture_output=True, text=True, check=True).stdout.splitlines()
        return [f for f in out if not (set(f.split("/")[:-1]) & SKIP_DIRS)]
    except (subprocess.CalledProcessError, FileNotFoundError):
        files = []
        for dp, dn, fs in os.walk(repo):
            dn[:] = [d for d in dn if d not in SKIP_DIRS]
            files += [os.path.relpath(os.path.join(dp, f), repo) for f in fs]
        return files


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("repo")
    ap.add_argument("--out", default="spec-candidates.json")
    ap.add_argument("--include", nargs="*", default=[], help="only paths matching these globs")
    ap.add_argument("--exclude", nargs="*", default=[], help="skip paths matching these globs")
    args = ap.parse_args()
    repo = os.path.abspath(args.repo)
    compiled = {k: [(lab, ext, re.compile(rx, re.M)) for lab, ext, rx in v] for k, v in P.items()}

    hits, skipped, langs = defaultdict(list), Counter(), Counter()
    for rel in sorted(list_files(repo)):
        if SECRET.search(rel):
            skipped["likely secret"] += 1
            continue
        if args.include and not any(fnmatch.fnmatch(rel, g) for g in args.include):
            continue
        if any(fnmatch.fnmatch(rel, g) for g in args.exclude):
            continue
        ext = os.path.splitext(rel)[1].lower()
        path = os.path.join(repo, rel)
        try:
            if os.path.getsize(path) > MAX_BYTES:
                skipped["too large"] += 1
                continue
            text = open(path, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        langs[ext or "(none)"] += 1
        is_test = bool(TEST.search(rel))
        for kind, pats in compiled.items():
            for label, exts, rx in pats:
                if exts and ext not in exts:
                    continue
                if rx.pattern.startswith("__FILE__"):
                    if re.search(rx.pattern[8:], rel):
                        hits[kind].append({"label": label, "file": rel, "line": 1, "name": rel, "test": is_test})
                    continue
                if exts is None and ext not in {".py", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".go",
                                                ".java", ".kt", ".rb", ".php", ".cs", ".rs", ".prisma", ".sql"}:
                    continue
                for m in rx.finditer(text):
                    line = text.count("\n", 0, m.start()) + 1
                    name = next((g for g in reversed(m.groups()) if g), None) if m.groups() else None
                    snippet = text.splitlines()[line - 1].strip()[:140]
                    hits[kind].append({"label": label, "file": rel, "line": line,
                                       "name": name or snippet, "test": is_test})

    result = {"repo": repo, "languages": dict(langs.most_common()), "skipped": dict(skipped),
              "candidates": {k: v for k, v in hits.items()}}
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)

    print(f"candidates: {args.out}")
    print("files by extension: " + ", ".join(f"{e} {n}" for e, n in langs.most_common(8)))
    if skipped:
        print("skipped: " + ", ".join(f"{k} {v}" for k, v in skipped.items()))
    for kind in P:
        items = [h for h in hits.get(kind, []) if not h["test"]]
        by_label = Counter(h["label"] for h in items)
        print(f"\n{kind}: {len(items)} (+{len(hits.get(kind, [])) - len(items)} in tests)  "
              + ", ".join(f"{l} {n}" for l, n in by_label.most_common()))
        files = Counter(h["file"] for h in items)
        for f, n in files.most_common(6):
            print(f"    {n:4d}  {f}")


if __name__ == "__main__":
    main()
