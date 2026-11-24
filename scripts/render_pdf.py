#!/usr/bin/env python3
"""Render SPEC_DIR/spec.md to SPEC_DIR/spec.pdf, locally, with headless Chrome.

Usage: render_pdf.py SPEC_DIR [--source-url URL] [--force]

Markdown is converted to HTML (Python-Markdown) and printed to PDF by a local
Chrome or Chromium; nothing is sent to a remote service. Evidence links
(`/path/file.py#L12`) become links to the source on the hosting site, pinned
to the current commit: `--source-url` overrides the base (for example
`https://github.com/org/repo/blob/<sha>`), otherwise it is derived from the
`origin` remote and HEAD. Diagrams and prototypes are embedded from their SVG;
a diagram not yet rendered shows a note instead.

Next to the PDF, `spec.pdf.sha256` records a fingerprint of everything the PDF
was made from (spec.md and the SVGs). `check_spec.py` warns when it no longer
matches, so a spec change without a new PDF is caught. The PDF is rebuilt only
when the fingerprint changed, unless --force.

Exit code 2 when Chrome/Chromium or the `markdown` package is unavailable
(with `uv` on PATH the package is fetched into a throwaway environment).
"""
import argparse
import hashlib
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile

FINGERPRINT = "spec.pdf.sha256"
CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
]

CSS = """
@page { size: A4; margin: 16mm 14mm; }
body { font-family: -apple-system, "PingFang SC", "Noto Sans CJK SC", "Microsoft YaHei",
       "Segoe UI", sans-serif; font-size: 10pt; line-height: 1.55; color: #1a1a1a; }
h1 { font-size: 20pt; border-bottom: 2px solid #333; padding-bottom: 4px; }
h2 { font-size: 15pt; border-bottom: 1px solid #bbb; padding-bottom: 3px; margin-top: 1.8em; }
h3 { font-size: 12.5pt; margin-top: 1.4em; }
h4 { font-size: 11pt; } h5 { font-size: 10pt; }
h2, h3, h4, h5 { break-after: avoid; }
table { border-collapse: collapse; width: 100%; margin: .6em 0; font-size: 9pt; }
th, td { border: 1px solid #ccc; padding: 3px 6px; vertical-align: top; text-align: left; }
th { background: #f2f2f2; }
tr { break-inside: avoid; }
code { font-family: "SF Mono", Menlo, "Noto Sans Mono CJK SC", monospace; font-size: 8.5pt;
       background: #f4f4f4; padding: 0 2px; border-radius: 2px; }
pre { background: #f7f7f7; border: 1px solid #e3e3e3; padding: 8px; font-size: 8pt;
      line-height: 1.35; white-space: pre-wrap; break-inside: avoid; }
pre code { background: none; padding: 0; }
blockquote { color: #555; border-left: 3px solid #ccc; margin-left: 0; padding-left: 10px; }
a { color: #0b5cad; text-decoration: none; }
img { max-width: 100%; break-inside: avoid; }
.missing-diagram { color: #a33; font-style: italic; }
"""


def fingerprint(spec_dir):
    """Hash of spec.md and every SVG it can embed, in a stable order."""
    h = hashlib.sha256()
    files = [os.path.join(spec_dir, "spec.md")]
    for sub in ("diagrams", "prototypes"):
        d = os.path.join(spec_dir, sub)
        if os.path.isdir(d):
            files += [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith(".svg")]
    for path in files:
        if os.path.exists(path):
            h.update(os.path.relpath(path, spec_dir).encode() + b"\0")
            with open(path, "rb") as fh:
                h.update(fh.read())
            h.update(b"\0")
    return h.hexdigest()


def find_chrome():
    env = os.environ.get("CHROME")
    for c in ([env] if env else []) + CHROME_CANDIDATES:
        if os.path.isfile(c) or shutil.which(c):
            return c if os.path.isfile(c) else shutil.which(c)
    return None


def git(repo, *args):
    try:
        return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True,
                              check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def default_source_url(spec_dir):
    remote = git(spec_dir, "remote", "get-url", "origin")
    sha = git(spec_dir, "rev-parse", "HEAD")
    m = re.match(r"(?:git@|ssh://git@|https://)([^/:]+)[/:](.+?)(?:\.git)?/?$", remote)
    if not (m and sha):
        return None
    return f"https://{m.group(1)}/{m.group(2)}/blob/{sha}"


def slugify(value, separator="-"):
    """GitHub-style heading ids, so `[订单](#订单)` links work in the PDF too."""
    value = re.sub(r"[^\w\- ]", "", value.strip().lower())
    return value.replace(" ", separator)


def to_html(spec_dir, source_url):
    import markdown  # imported here so --help works without it

    text = open(os.path.join(spec_dir, "spec.md"), encoding="utf-8").read()
    body = markdown.markdown(
        text, extensions=["tables", "fenced_code", "sane_lists", "toc"],
        extension_configs={"toc": {"slugify": slugify}},
    )

    def link(m):
        href = html.unescape(m.group(1))
        if href.startswith("/") and source_url:
            path, _, anchor = href.partition("#")
            href = source_url + path + (("#" + anchor) if anchor else "")
        return f'href="{html.escape(href, quote=True)}"'

    body = re.sub(r'href="([^"]*)"', link, body)

    def image(m):
        src = html.unescape(m.group(2))
        if re.match(r"[a-z]+:", src) or os.path.exists(os.path.join(spec_dir, src)):
            return m.group(0)
        puml = src[:-4] + ".puml" if src.endswith(".svg") else src
        return f'<span class="missing-diagram">〔图未渲染：{html.escape(puml)}〕</span>'

    body = re.sub(r'<img ([^>]*?)src="([^"]*)"([^>]*)>', image, body)
    title = re.search(r"^# (.+)$", text, re.M)
    return (f'<!doctype html><html lang="zh"><head><meta charset="utf-8">'
            f"<title>{html.escape(title.group(1) if title else 'spec')}</title>"
            f"<style>{CSS}</style></head><body>{body}</body></html>")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("spec_dir")
    ap.add_argument("--source-url", help="base URL for evidence links (default: origin remote at HEAD)")
    ap.add_argument("--force", action="store_true", help="rebuild even if nothing changed")
    args = ap.parse_args()
    spec_dir = os.path.abspath(args.spec_dir)
    if not os.path.exists(os.path.join(spec_dir, "spec.md")):
        sys.exit(f"no spec.md in {spec_dir}")

    try:
        import markdown  # noqa: F401
    except ImportError:
        if shutil.which("uv") and not os.environ.get("PM_SPEC_PDF_REEXEC"):
            env = dict(os.environ, PM_SPEC_PDF_REEXEC="1")
            cmd = ["uv", "run", "--quiet", "--no-project", "--with", "markdown",
                   "python3", os.path.abspath(__file__), *sys.argv[1:]]
            sys.exit(subprocess.run(cmd, env=env).returncode)
        print("the `markdown` package is missing: pip install markdown (or install uv)",
              file=sys.stderr)
        sys.exit(2)

    pdf, fp_file = os.path.join(spec_dir, "spec.pdf"), os.path.join(spec_dir, FINGERPRINT)
    fp = fingerprint(spec_dir)
    if not args.force and os.path.exists(pdf) and os.path.exists(fp_file):
        if open(fp_file).read().strip() == fp:
            print("spec.pdf is up to date")
            return

    chrome = find_chrome()
    if not chrome:
        print("no Chrome or Chromium found; install one or set CHROME to its path", file=sys.stderr)
        sys.exit(2)

    source_url = args.source_url or default_source_url(spec_dir)
    # Written inside SPEC_DIR so relative image paths resolve; removed afterwards.
    fd, page = tempfile.mkstemp(prefix=".spec-print-", suffix=".html", dir=spec_dir)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(to_html(spec_dir, source_url))
    tmp_pdf = pdf + ".part"
    try:
        with tempfile.TemporaryDirectory() as profile:
            r = subprocess.run([
                chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
                "--no-pdf-header-footer", f"--user-data-dir={profile}",
                "--allow-file-access-from-files", f"--print-to-pdf={tmp_pdf}",
                "file://" + page,
            ], capture_output=True, text=True, timeout=300)
    finally:
        os.remove(page)
    if r.returncode != 0 or not os.path.exists(tmp_pdf):
        print(r.stderr[-2000:], file=sys.stderr)
        sys.exit(1)
    os.replace(tmp_pdf, pdf)
    with open(fp_file, "w") as fh:
        fh.write(fp + "\n")
    print(f"wrote {os.path.relpath(pdf)} ({os.path.getsize(pdf) // 1024} KB)"
          + ("" if source_url else "; evidence links left repository-relative"))


if __name__ == "__main__":
    main()
