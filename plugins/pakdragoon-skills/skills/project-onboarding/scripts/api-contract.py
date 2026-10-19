#!/usr/bin/env python3
"""api-contract.py: heuristically match frontend API calls to backend routes.

Usage:
  python3 api-contract.py --backend BE --frontend FE [--backend other-be] [--frontend admin] [--root .]

Paths in the report are relative to --root (default: current directory), so they can be
used directly as citations in the onboarding page.

Backend routes detected: NestJS (@Controller + @Get/@Post/..., setGlobalPrefix), Express /
Fastify / Koa-router / Hono / gin / echo style `x.get('/path')`, FastAPI / Flask decorators,
Spring @*Mapping, Laravel Route::get, Next.js pages/api and app/**/route.ts.
Frontend calls detected: fetch(), axios / ky / ofetch / custom clients `x.get('/path')`,
Angular HttpClient, and path-like string literals in api/service/endpoint files.

This is a heuristic. Treat matches as leads to verify, never as Confirmed on their own.
"""
import argparse
import os
import re
import subprocess
import sys
from collections import defaultdict

SKIP_DIRS = {"node_modules", "dist", "build", ".next", "out", "coverage", "vendor", ".git",
             "__pycache__", ".venv", "venv", "target", ".nuxt", ".svelte-kit"}
BE_EXT = {".ts", ".js", ".mjs", ".cjs", ".py", ".go", ".java", ".kt", ".php", ".rb", ".cs"}
FE_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".vue", ".svelte", ".dart"}
TEST_RE = re.compile(r"(\.|_)(test|spec)\.[a-z]+$|(^|/)(__tests__|tests?|e2e|cypress|__mocks__|mocks?)/", re.I)
HTTP_VERBS = ("get", "post", "put", "patch", "delete", "options", "head", "all")

# ---------- helpers ----------

def list_files(repo, exts):
    try:
        out = subprocess.run(["git", "-C", repo, "-c", "core.quotepath=off", "ls-files", "-z"],
                             capture_output=True, text=True, check=True).stdout
        files = [f for f in out.split("\0") if f]
    except (subprocess.CalledProcessError, FileNotFoundError):
        files = []
        for dp, dns, fns in os.walk(repo):
            dns[:] = [d for d in dns if d not in SKIP_DIRS]
            for fn in fns:
                files.append(os.path.relpath(os.path.join(dp, fn), repo))
    keep = []
    for f in files:
        parts = f.split("/")
        if any(p in SKIP_DIRS for p in parts[:-1]):
            continue
        if os.path.splitext(f)[1].lower() in exts and not TEST_RE.search(f) and not f.endswith(".d.ts"):
            keep.append(f)
    return keep


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def line_of(text, idx):
    return text.count("\n", 0, idx) + 1


PARAM_RES = [
    re.compile(r"\$\{[^}]*\}"),       # ${id}
    re.compile(r":[A-Za-z_]\w*\??"),   # :id
    re.compile(r"\{[A-Za-z_][^}/]*\}"),  # {id}
    re.compile(r"<[^>/]+>"),           # <int:id>
    re.compile(r"\[\[?\.{0,3}[^\]/]+\]?\]"),  # [id], [...slug]
]


def normalize(path):
    """Return a comparable path: params -> :p, no query, no trailing slash, lowercase."""
    p = path.strip()
    p = re.sub(r"^[a-z]+://[^/]+", "", p, flags=re.I)  # full URL -> path
    p = p.split("?")[0].split("#")[0]
    for rx in PARAM_RES:
        p = rx.sub(":p", p)
    p = re.sub(r"/+", "/", p)
    if not p.startswith("/"):
        p = "/" + p
    if len(p) > 1:
        p = p.rstrip("/")
    return p.lower()


def strip_prefix(norm):
    """Drop leading api/version segments so '/api/v1/users' and '/users' compare equal."""
    segs = [s for s in norm.split("/") if s]
    while segs and re.fullmatch(r"api|v\d+(\.\d+)?|rest|public|internal", segs[0]):
        segs.pop(0)
    return "/" + "/".join(segs)


def join(*parts):
    out = "/".join(p.strip("/") for p in parts if p and p.strip("/"))
    return "/" + out


# ---------- backend extraction ----------

NEST_CTRL = re.compile(r"@Controller\(\s*(?:(['\"`])([^'\"`]*)\1|\{[^}]*?path\s*:\s*(['\"`])([^'\"`]*)\3[^}]*\})?\s*\)")
NEST_METHOD = re.compile(r"@(Get|Post|Put|Patch|Delete|All|Options|Head)\(\s*(?:(['\"`])([^'\"`]*)\2)?\s*\)")
NEST_PREFIX = re.compile(r"setGlobalPrefix\(\s*(['\"`])([^'\"`]+)\1")
GENERIC_ROUTE = re.compile(r"\b([A-Za-z_]\w*)\.(get|post|put|patch|delete|all|GET|POST|PUT|PATCH|DELETE|Any|any)\(\s*(['\"`])(/[^'\"`]*)\3")
FLASK_ROUTE = re.compile(r"@\w+\.route\(\s*(['\"])(/[^'\"]*)\1([^)]*)\)")
SPRING_MAP = re.compile(r"@(Get|Post|Put|Patch|Delete|Request)Mapping\(\s*(?:(?:value|path)\s*=\s*)?\{?\s*\"([^\"]*)\"")
SPRING_CLASS = re.compile(r"@RequestMapping\(\s*(?:(?:value|path)\s*=\s*)?\{?\s*\"([^\"]*)\"[^)]*\)\s*(?:@\w+(?:\([^)]*\))?\s*)*(?:public\s+)?(?:abstract\s+)?class\b")
LARAVEL = re.compile(r"Route::(get|post|put|patch|delete|any|match)\(\s*(['\"])([^'\"]*)\2")
MOUNT = re.compile(r"\b(?:app|router|server)\.(?:use|register|route|group)\(\s*(['\"`])(/[^'\"`]*)\1")
NEXT_APP_METHOD = re.compile(r"export\s+(?:async\s+)?(?:function|const)\s+(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b")


def backend_routes(repo, root):
    routes, prefixes, mounts = [], [], []
    for rel in list_files(repo, BE_EXT):
        full = os.path.join(repo, rel)
        text = read(full)
        if not text:
            continue
        cite = os.path.relpath(full, root)
        ext = os.path.splitext(rel)[1]

        for m in NEST_PREFIX.finditer(text):
            prefixes.append((m.group(2), f"{cite}:{line_of(text, m.start())}"))

        # Next.js API routes from file paths.
        mpages = re.search(r"(?:^|/)pages/api/(.+)\.(?:ts|js)$", rel)
        mapp = re.search(r"(?:^|/)app/(.*?)/?route\.(?:ts|js)$", rel)
        if mpages:
            sub = re.sub(r"/index$", "", mpages.group(1))
            routes.append(("ANY", "/api/" + sub, f"{cite}:1", "next-pages"))
        elif mapp and "/api" in "/" + mapp.group(1):
            path = "/" + re.sub(r"\([^)]*\)/?", "", mapp.group(1))  # drop (groups)
            verbs = NEXT_APP_METHOD.findall(text) or ["ANY"]
            for v in verbs:
                routes.append((v.upper(), path, f"{cite}:1", "next-app"))

        if "@Controller" in text:
            events = [(m.start(), "c", m) for m in NEST_CTRL.finditer(text)]
            events += [(m.start(), "m", m) for m in NEST_METHOD.finditer(text)]
            ctrl = ""
            for pos, kind, m in sorted(events, key=lambda e: e[0]):
                if kind == "c":
                    ctrl = m.group(2) or m.group(4) or ""
                else:
                    routes.append((m.group(1).upper(), join(ctrl, m.group(3) or ""),
                                   f"{cite}:{line_of(text, pos)}", "nestjs"))

        if ext in (".java", ".kt") and "Mapping" in text:
            cls = SPRING_CLASS.search(text)
            base = cls.group(1) if cls else ""
            for m in SPRING_MAP.finditer(text):
                if cls and m.start() == cls.start():
                    continue
                verb = "ANY" if m.group(1) == "Request" else m.group(1).upper()
                routes.append((verb, join(base, m.group(2)), f"{cite}:{line_of(text, m.start())}", "spring"))

        if ext == ".php":
            for m in LARAVEL.finditer(text):
                verb = m.group(1).upper()
                routes.append(("ANY" if verb in ("ANY", "MATCH") else verb, join(m.group(3)),
                               f"{cite}:{line_of(text, m.start())}", "laravel"))

        if ext == ".py":
            for m in FLASK_ROUTE.finditer(text):
                verbs = re.findall(r"['\"](GET|POST|PUT|PATCH|DELETE)['\"]", m.group(3), re.I) or ["ANY"]
                for v in verbs:
                    routes.append((v.upper(), m.group(2), f"{cite}:{line_of(text, m.start())}", "flask"))

        for m in GENERIC_ROUTE.finditer(text):
            obj = m.group(1)
            if obj in ("axios", "http", "https", "request", "fetch", "client", "httpService", "this", "res", "req",
                       "map", "params", "headers", "query", "cache", "redis", "config", "configService", "process"):
                continue
            verb = m.group(2).upper()
            routes.append(("ANY" if verb == "ALL" else verb, m.group(4),
                           f"{cite}:{line_of(text, m.start())}", "router"))

        for m in MOUNT.finditer(text):
            mounts.append((m.group(2), f"{cite}:{line_of(text, m.start())}"))

    # De-duplicate.
    seen, uniq = set(), []
    for r in routes:
        key = (r[0], normalize(r[1]), r[2])
        if key not in seen:
            seen.add(key)
            uniq.append(r)
    return uniq, prefixes, mounts


# ---------- frontend extraction ----------

CALL = re.compile(r"(?P<callee>\b(?:[A-Za-z_$][\w$]*\.)*[A-Za-z_$][\w$]*)\s*(?:<[^>()]{0,80}>)?\(\s*(?P<q>['\"`])(?P<url>[^'\"`\n]{1,200}?)(?P=q)")
CALLEE_VERB = re.compile(r"(?:^|\.)(get|post|put|patch|delete|del|head|options|request|fetch|\$fetch|ofetch|useFetch|useSWR|useQuery|ky|api|http|apiClient|client|instance)$", re.I)
METHOD_OPT = re.compile(r"method\s*:\s*['\"`](GET|POST|PUT|PATCH|DELETE)['\"`]", re.I)
API_FILE = re.compile(r"(^|/)(api|apis|services?|endpoints?|requests?|http|clients?|queries|mutations|hooks|store|redux|slices?)(/|\.|$)|api|service|endpoint|query|mutation", re.I)
PATH_LIT = re.compile(r"(['\"`])(/(?:[A-Za-z0-9_\-]+|\$\{[^}]+\}|:[A-Za-z_]\w*)(?:/(?:[A-Za-z0-9_\-.]+|\$\{[^}]+\}|:[A-Za-z_]\w*))*/?)\1")
NOT_API = re.compile(r"\.(png|jpe?g|svg|gif|webp|ico|css|scss|woff2?|ttf|mp4|pdf|json|html)$|^/(static|assets|images?|img|icons?|fonts?)/", re.I)


def clean_fe_url(url):
    u = url.strip()
    u = re.sub(r"^[a-z]+://[^/]+", "", u, flags=re.I)
    # Leading ${baseUrl} / ${API_URL}: drop it.
    while u.startswith("${"):
        end = u.find("}")
        if end == -1:
            return None
        u = u[end + 1:]
    if not u.startswith("/") or u.startswith("//"):
        return None
    if NOT_API.search(u.split("?")[0]):
        return None
    if not re.search(r"[A-Za-z]", u):
        return None
    return u


def frontend_calls(repo, root):
    calls = []
    for rel in list_files(repo, FE_EXT):
        full = os.path.join(repo, rel)
        text = read(full)
        if not text:
            continue
        cite = os.path.relpath(full, root)
        found_spans = []
        for m in CALL.finditer(text):
            callee = m.group("callee")
            if not CALLEE_VERB.search(callee):
                continue
            last = callee.split(".")[-1].lower()
            if last in ("navigate", "push", "replace", "redirect", "link", "route", "router", "t", "i18n", "require", "import"):
                continue
            url = clean_fe_url(m.group("url"))
            if not url:
                continue
            if last in ("get", "post", "put", "patch", "delete", "head", "options"):
                verb = last.upper()
            elif last == "del":
                verb = "DELETE"
            else:
                opt = METHOD_OPT.search(text, m.end(), m.end() + 300)
                verb = opt.group(1).upper() if opt else ("GET" if "fetch" in last.lower() else "?")
            calls.append((verb, url, f"{cite}:{line_of(text, m.start())}", "call"))
            found_spans.append((m.start("url"), m.end("url")))
        if API_FILE.search(rel):
            for m in PATH_LIT.finditer(text):
                if any(a <= m.start(2) < b for a, b in found_spans):
                    continue
                url = clean_fe_url(m.group(2))
                if not url or url.count("/") < 1:
                    continue
                calls.append(("?", url, f"{cite}:{line_of(text, m.start())}", "literal"))
    return calls


# ---------- matching ----------

def verb_ok(a, b):
    return a in ("?", "ANY") or b in ("?", "ANY") or a == b


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", action="append", default=[], help="backend repo dir (repeatable)")
    ap.add_argument("--frontend", action="append", default=[], help="frontend repo dir (repeatable)")
    ap.add_argument("--root", default=".", help="workspace root; report paths are relative to it")
    ap.add_argument("--limit", type=int, default=150, help="max rows per table")
    a = ap.parse_args()
    if not a.backend or not a.frontend:
        ap.error("need at least one --backend and one --frontend")
    root = os.path.abspath(a.root)

    routes, prefixes, mounts = [], [], []
    for b in a.backend:
        r, p, mo = backend_routes(os.path.abspath(b), root)
        routes += r; prefixes += p; mounts += mo
    calls = []
    for f in a.frontend:
        calls += frontend_calls(os.path.abspath(f), root)

    global_prefixes = sorted({normalize(p[0]) for p in prefixes})

    def be_keys(path):
        n = normalize(path)
        keys = {n, strip_prefix(n)}
        for gp in global_prefixes:
            keys.add(normalize(gp + "/" + path))
        return keys

    index = defaultdict(list)
    for i, (verb, path, cite, kind) in enumerate(routes):
        for k in be_keys(path):
            index[k].append(i)

    matched = defaultdict(list)          # route idx -> [call]
    fe_unmatched = []
    for c in calls:
        verb, url, cite, kind = c
        n = normalize(url)
        cand = index.get(n, []) + index.get(strip_prefix(n), [])
        hits = sorted({i for i in cand if verb_ok(verb, routes[i][0])})
        if hits:
            for i in hits:
                matched[i].append(c)
        elif kind == "call":
            fe_unmatched.append(c)

    be_unused = [r for i, r in enumerate(routes) if i not in matched]

    def calls_cell(cs):
        cites = []
        for c in cs:
            if c[2] not in cites:
                cites.append(c[2])
        more = f" +{len(cites) - 3} more" if len(cites) > 3 else ""
        return ", ".join(f"`{x}`" for x in cites[:3]) + more

    print("# API contract (frontend calls vs backend routes)")
    print()
    print("_Heuristic static match. Use as leads; verify before marking anything Confirmed._")
    print()
    print(f"- Backend dirs: {', '.join('`' + os.path.relpath(os.path.abspath(b), root) + '`' for b in a.backend)}")
    print(f"- Frontend dirs: {', '.join('`' + os.path.relpath(os.path.abspath(f), root) + '`' for f in a.frontend)}")
    print(f"- Backend routes found: {len(routes)}  |  frontend call sites: {sum(1 for c in calls if c[3] == 'call')}"
          f" (+{sum(1 for c in calls if c[3] == 'literal')} path literals)")
    print(f"- Matched routes: {len(matched)}  |  FE calls with no BE route: {len(fe_unmatched)}  |  BE routes with no FE caller: {len(be_unused)}")
    kinds = defaultdict(int)
    for r in routes:
        kinds[r[3]] += 1
    if kinds:
        print("- Route styles detected: " + ", ".join(f"{k} ({v})" for k, v in sorted(kinds.items())))
    if prefixes:
        print("- Global prefixes: " + ", ".join(f"`{p}` at `{c}`" for p, c in prefixes))
    if mounts:
        print("- Router mounts (prefixes NOT applied to routes above; check manually): "
              + ", ".join(f"`{p}` at `{c}`" for p, c in mounts[:20]) + (" ..." if len(mounts) > 20 else ""))

    print("\n## Matched\n")
    print("| method | backend route | defined at | called from |")
    print("|---|---|---|---|")
    for i in sorted(matched, key=lambda i: normalize(routes[i][1]))[: a.limit]:
        verb, path, cite, _ = routes[i]
        print(f"| {verb} | `{path}` | `{cite}` | {calls_cell(matched[i])} |")

    print("\n## Frontend calls with no matching backend route\n")
    print("_Could be an external API, a removed endpoint, a dynamic prefix this script can't resolve, or a real bug._\n")
    if fe_unmatched:
        print("| method | url | called from |")
        print("|---|---|---|")
        grouped = defaultdict(list)
        for c in fe_unmatched:
            grouped[(c[0], c[1])].append(c)
        for (verb, url), cs in sorted(grouped.items(), key=lambda kv: normalize(kv[0][1]))[: a.limit]:
            print(f"| {verb} | `{url}` | {calls_cell(cs)} |")
    else:
        print("_none_")

    print("\n## Backend routes with no frontend caller\n")
    print("_Could be used by mobile apps, webhooks, third parties, cron, admin tools, or be dead._\n")
    if be_unused:
        print("| method | route | defined at |")
        print("|---|---|---|")
        for verb, path, cite, _ in sorted(be_unused, key=lambda r: normalize(r[1]))[: a.limit]:
            print(f"| {verb} | `{path}` | `{cite}` |")
    else:
        print("_none_")
    return 0


if __name__ == "__main__":
    sys.exit(main())
