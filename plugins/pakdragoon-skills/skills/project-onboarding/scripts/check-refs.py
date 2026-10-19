#!/usr/bin/env python3
"""check-refs.py: verify citations in a generated onboarding page.

Usage: python3 check-refs.py <onboarding.html> [--root <repo-root>]

Checks every <code class="ref ...">...</code>:
  - file refs  "path", "path:12", "path:12-40"  -> file is tracked/exists, lines within file length
  - commit refs (class contains "commit")        -> commit exists in the repo
  - material refs (class contains "material")    -> skipped
Also reports leftover <!-- FILL markers and secret-looking strings.
Exit code 1 if anything is broken.
"""
import html
import os
import re
import subprocess
import sys

REF_RE = re.compile(r'<code\s+class="([^"]*\bref\b[^"]*)"\s*>(.*?)</code>', re.S)
FILE_RE = re.compile(r'^(?P<path>[^\s:]+?)(?::(?P<a>\d+)(?:-(?P<b>\d+))?)?$')
SECRET_RES = [
    (re.compile(r'AKIA[0-9A-Z]{16}'), "AWS access key id"),
    (re.compile(r'(?i)(password|passwd|secret|api[_-]?key|token)\s*[=:]\s*["\']?[^\s"\'<]{6,}'), "credential assignment"),
    (re.compile(r'[a-z][a-z0-9+.-]*://[^\s/:@<"]+:[^\s/@<"]+@'), "credentials in URL"),
    (re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----'), "private key"),
    (re.compile(r'\b(sk|pk|rk)_(live|test)_[0-9A-Za-z]{10,}'), "Stripe-style key"),
    (re.compile(r'\bgh[pousr]_[0-9A-Za-z]{30,}'), "GitHub token"),
    (re.compile(r'\bxox[abpr]-[0-9A-Za-z-]{10,}'), "Slack token"),
    (re.compile(r'\b(10\.\d{1,3}|192\.168|172\.(1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b'), "private IP"),
    (re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+'), "email address"),
]


def git(root, *args):
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    page = args[0]
    root = None
    if "--root" in args:
        root = args[args.index("--root") + 1]
    if root is None:
        r = git(os.path.dirname(os.path.abspath(page)), "rev-parse", "--show-toplevel")
        root = r.stdout.strip() or os.getcwd()

    text = open(page, encoding="utf-8").read()
    problems = []
    line_cache = {}
    checked = 0

    for cls, raw in REF_RE.findall(text):
        ref = html.unescape(re.sub(r"<[^>]+>", "", raw)).strip()
        classes = cls.split()
        if "material" in classes:
            continue
        checked += 1
        if "commit" in classes:
            if git(root, "cat-file", "-e", f"{ref}^{{commit}}").returncode != 0:
                problems.append(f"commit not found: {ref}")
            continue
        m = FILE_RE.match(ref)
        if not m:
            problems.append(f"unparseable ref: {ref}")
            continue
        path = m.group("path")
        if path.startswith("./"):
            path = path[2:]
        full = os.path.join(root, path)
        if not os.path.exists(full):
            problems.append(f"missing file: {ref}")
            continue
        if m.group("a") and os.path.isfile(full):
            if full not in line_cache:
                try:
                    with open(full, encoding="utf-8", errors="replace") as fh:
                        line_cache[full] = sum(1 for _ in fh)
                except OSError:
                    line_cache[full] = None
            n = line_cache[full]
            hi = int(m.group("b") or m.group("a"))
            if n is not None and hi > n:
                problems.append(f"line out of range: {ref} (file has {n} lines)")

    fills = len(re.findall(r"<!--\s*FILL", text))
    if fills:
        problems.append(f"{fills} unfilled <!-- FILL --> marker(s) remain")

    visible = re.sub(r"<script.*?</script>|<style.*?</style>", "", text, flags=re.S)
    for rx, label in SECRET_RES:
        for hit in sorted(set(m.group(0) for m in rx.finditer(visible)))[:5]:
            if label == "email address" and hit.endswith(("@example.com", "@users.noreply.github.com")):
                continue
            problems.append(f"possible {label}: {hit[:60]}")

    print(f"Checked {checked} references in {page} (repo root: {root})")
    if problems:
        print(f"{len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("All references resolve. No leftover markers or secret-looking strings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
