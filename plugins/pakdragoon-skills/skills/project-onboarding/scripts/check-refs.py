#!/usr/bin/env python3
"""check-refs.py: verify citations in a generated onboarding page.

Usage: python3 check-refs.py <onboarding.html> [--root <repo-or-workspace-root>]

Single-repo mode: refs are repo-relative ("src/app.ts:12"), commits are "a1b2c3d".
Workspace mode:   refs are workspace-relative ("BE/src/app.ts:12"), commits are
                  "BE@a1b2c3d" (a bare hash is accepted if it exists in any child repo).
If --root is omitted: the git top-level of the page's folder, else the parent of an
".onboarding" folder, else the current directory.

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


def child_repos(root, depth=3):
    found = []
    base = root.rstrip(os.sep).count(os.sep)
    for dp, dns, _ in os.walk(root):
        if ".git" in dns or os.path.isfile(os.path.join(dp, ".git")):
            if dp != root:
                found.append(dp)
                dns[:] = []
                continue
        dns[:] = [d for d in dns if d not in ("node_modules", "vendor", "dist", "build", ".git", ".venv")
                  and dp.count(os.sep) - base < depth]
    return found


def commit_exists(repo, h):
    return git(repo, "cat-file", "-e", f"{h}^{{commit}}").returncode == 0


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
        page_dir = os.path.dirname(os.path.abspath(page))
        r = git(page_dir, "rev-parse", "--show-toplevel")
        if r.returncode == 0 and r.stdout.strip():
            root = r.stdout.strip()
        elif os.path.basename(page_dir) == ".onboarding":
            root = os.path.dirname(page_dir)
        else:
            root = os.getcwd()
    root = os.path.abspath(root)
    root_is_repo = git(root, "rev-parse", "--git-dir").returncode == 0
    children = [] if root_is_repo else child_repos(root)

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
            if "@" in ref:
                repo_rel, h = ref.split("@", 1)
                ok = commit_exists(os.path.join(root, repo_rel), h)
            else:
                ok = any(commit_exists(r, ref) for r in ([root] if root_is_repo else children))
            if not ok:
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

    mode = "repo" if root_is_repo else f"workspace, {len(children)} repos"
    print(f"Checked {checked} references in {page} (root: {root}, {mode})")
    if problems:
        print(f"{len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("All references resolve. No leftover markers or secret-looking strings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
