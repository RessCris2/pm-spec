#!/usr/bin/env python3
"""Render SPEC_DIR/diagrams/*.puml to SVG next to each source, locally.

Usage: render_diagrams.py SPEC_DIR [--all]

Uses `plantuml` on PATH, or `java -jar $PLANTUML_JAR`. Never sends diagrams
to a remote rendering server: they describe private code. Only sources newer
than their SVG are rendered unless --all is given. Exit code 2 when no
renderer is available, 1 when a diagram fails to render.
"""
import argparse
import os
import shutil
import subprocess
import sys


def renderer():
    if shutil.which("plantuml"):
        return ["plantuml"]
    jar = os.environ.get("PLANTUML_JAR")
    if jar and os.path.isfile(jar) and shutil.which("java"):
        return ["java", "-jar", jar]
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("spec_dir")
    ap.add_argument("--all", action="store_true", help="re-render every diagram")
    args = ap.parse_args()
    d = os.path.join(os.path.abspath(args.spec_dir), "diagrams")
    if not os.path.isdir(d):
        print("no diagrams directory; nothing to render")
        return
    todo = []
    for f in sorted(os.listdir(d)):
        if f.endswith(".puml"):
            src, svg = os.path.join(d, f), os.path.join(d, f[:-5] + ".svg")
            if args.all or not os.path.exists(svg) or os.path.getmtime(svg) < os.path.getmtime(src):
                todo.append(src)
    if not todo:
        print("all diagrams up to date")
        return
    cmd = renderer()
    if not cmd:
        print("no PlantUML renderer found. Install one of:\n"
              "  macOS: brew install plantuml\n"
              "  Debian/Ubuntu: sudo apt-get install -y plantuml\n"
              "  or download plantuml.jar and set PLANTUML_JAR=/path/to/plantuml.jar (needs Java)\n"
              f"{len(todo)} diagrams not rendered", file=sys.stderr)
        sys.exit(2)
    failed = 0
    for src in todo:
        r = subprocess.run(cmd + ["-tsvg", "-charset", "UTF-8", src], capture_output=True, text=True)
        if r.returncode != 0:
            failed += 1
            print(f"FAILED {os.path.basename(src)}: {(r.stderr or r.stdout).strip()[:400]}", file=sys.stderr)
        else:
            print(f"rendered {os.path.basename(src)[:-5]}.svg")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
