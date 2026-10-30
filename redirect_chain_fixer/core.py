"""Find redirect chains and loops, and write the direct redirect rules that replace them.

Two ways in:
* map mode  - a redirect map (source, target), e.g. from your CMS, a plugin export or an old migration sheet.
               No network: chains are found by following the map itself.
* live mode - a list of URLs; each is requested hop by hop (redirects not followed automatically), so you
               see every status code and how long each hop took.

Why it matters: every extra hop is another request before the page starts to load. NP Digital found the
ranking score falls from 100 at 1 second to 92 at 2 seconds and 57 at 4 seconds (slug:
page-speed-seo-conversions). Rules: general best practice (Google follows up to 10 hops, but fewer is better;
301/308 for permanent moves).
"""
import time
from urllib.parse import urljoin, urlsplit

import pandas as pd
import requests

from .report import find_column

USER_AGENT = "redirect-chain-fixer/1.0 (+https://github.com/marketing-MEER/redirect-chain-fixer)"
MAX_HOPS = 10
PERMANENT = {301, 308}


# ---------------------------------------------------------------- map mode

def load_map(path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig", sep=None, engine="python", dtype=str).fillna("")
    s = find_column(df, ["source", "from", "old url", "old", "redirect from", "source url", "url"])
    t = find_column(df, ["target", "to", "new url", "new", "redirect to", "target url", "destination"])
    if s is None or t is None:
        if len(df.columns) < 2:
            raise ValueError("The map needs a source and a target column.")
        s, t = df.columns[:2]
    code = find_column(df, ["status", "code", "type", "status code", "http code"])
    out = pd.DataFrame({"source": df[s].str.strip(), "target": df[t].str.strip()})
    out["status"] = pd.to_numeric(df[code], errors="coerce").fillna(301).astype(int) if code else 301
    return out[(out["source"] != "") & (out["target"] != "")].reset_index(drop=True)


def _key_fn(urls):
    """Single-host maps: compare by path, so '/a' and 'https://site.com/a' are the same URL."""
    hosts = {urlsplit(u).netloc.lower() for u in urls if urlsplit(u).netloc}
    if len(hosts) <= 1:
        def key(u):
            p = urlsplit(u)
            path = p.path or "/"
            return path + (f"?{p.query}" if p.query else "")
        return key
    return lambda u: u.split("#")[0].replace(urlsplit(u).netloc, urlsplit(u).netloc.lower(), 1)


def flatten(m: pd.DataFrame) -> pd.DataFrame:
    """Follow each source through the map. One row per rule with the final target and the path taken."""
    cols = ["source", "target", "final_target", "hops", "issue", "fix", "path"]
    if m.empty:
        return pd.DataFrame([], columns=cols)
    key = _key_fn(list(m["source"]) + list(m["target"]))
    nxt, dupes = {}, set()
    for s, t, c in zip(m["source"], m["target"], m["status"]):
        k = key(s)
        if k in nxt:
            dupes.add(k)
            continue
        nxt[k] = (t, c)
    rows = []
    for s, t, c in zip(m["source"], m["target"], m["status"]):
        path, seen, cur, codes = [s], {key(s)}, t, [c]
        loop = False
        while True:
            path.append(cur)
            k = key(cur)
            if k in seen:
                loop = True
                break
            seen.add(k)
            if k not in nxt or len(path) > MAX_HOPS + 1:
                break
            cur, code = nxt[k]
            codes.append(code)
        hops = len(path) - 1
        issues = []
        if key(s) == key(t):
            issues.append("redirects to itself")
        elif loop:
            issues.append("loop")
        elif hops > 1:
            issues.append(f"chain ({hops} hops)")
        if any(code not in PERMANENT for code in codes):
            issues.append("temporary redirect in path")
        if key(s) in dupes:
            issues.append("source listed more than once")
        final = "" if loop else path[-1]
        if loop:
            fix = "Break the loop: point the source at the live page"
        elif hops > 1:
            fix = f"Change the target to {final}"
        elif "temporary redirect in path" in issues:
            fix = "Use 301 if the move is permanent"
        elif key(s) in dupes:
            fix = "Keep one rule per source; servers only use one of them"
        else:
            fix = ""
        rows.append({"source": s, "target": t, "final_target": final, "hops": hops,
                     "issue": "; ".join(issues), "fix": fix, "path": " -> ".join(path)})
    return pd.DataFrame(rows, columns=cols)


# ---------------------------------------------------------------- live mode

def load_urls(path) -> list[str]:
    p = str(path)
    if p.lower().endswith((".csv", ".tsv")):
        df = pd.read_csv(path, encoding="utf-8-sig", sep=None, engine="python", dtype=str).fillna("")
        col = find_column(df, ["url", "address", "source", "from", "old url", "page"]) or df.columns[0]
        urls = df[col].tolist()
    else:
        with open(path, encoding="utf-8-sig") as fh:
            urls = fh.read().splitlines()
    urls = [u.strip() for u in urls if u.strip().startswith(("http://", "https://"))]
    return list(dict.fromkeys(urls))


def trace(url: str, session=None, delay: float = 0.5, timeout: float = 20) -> dict:
    """Request a URL hop by hop. Returns the hops and a verdict."""
    session = session or requests.Session()
    session.headers.setdefault("User-Agent", USER_AGENT)
    hops, seen, cur, loop, error = [], set(), url, False, ""
    while len(hops) <= MAX_HOPS:
        if cur in seen:
            loop = True
            break
        seen.add(cur)
        if hops:
            time.sleep(max(delay, 0.5))
        try:
            resp = session.get(cur, allow_redirects=False, timeout=timeout)
        except requests.RequestException as exc:
            error = type(exc).__name__
            hops.append({"url": cur, "status": "failed", "ms": None})
            break
        hops.append({"url": cur, "status": resp.status_code, "ms": round(resp.elapsed.total_seconds() * 1000)})
        if 300 <= resp.status_code < 400 and resp.headers.get("Location"):
            cur = urljoin(cur, resp.headers["Location"])
        else:
            break
    redirects = [h for h in hops if isinstance(h["status"], int) and 300 <= h["status"] < 400]
    final = hops[-1]
    issues = []
    if loop:
        issues.append("loop")
    elif len(hops) > MAX_HOPS:
        issues.append("too many hops")
    if len(redirects) > 1 and not loop:
        issues.append(f"chain ({len(redirects)} hops)")
    if any(h["status"] not in PERMANENT for h in redirects):
        issues.append("temporary redirect in path")
    urls = [h["url"] for h in hops]
    if any(a.startswith("https://") and b.startswith("http://") for a, b in zip(urls, urls[1:])):
        issues.append("https to http")
    if not loop and len(hops) <= MAX_HOPS and final["status"] != 200:
        issues.append(f"ends in {final['status']}" + (f" ({error})" if error else ""))
    redirect_ms = sum(h["ms"] or 0 for h in hops[:-1]) if redirects else 0
    return {"url": url, "final_url": "" if loop else final["url"], "final_status": final["status"],
            "redirects": len(redirects), "redirect_ms": redirect_ms, "issue": "; ".join(issues),
            "path": " -> ".join(f"{h['url']} [{h['status']}]" for h in hops) + (f" -> back to {cur}" if loop else "")}


def trace_all(urls, delay: float = 0.5, session=None, progress=None) -> pd.DataFrame:
    cols = ["url", "final_url", "final_status", "redirects", "redirect_ms", "issue", "fix", "path"]
    session = session or requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    rows = []
    for i, u in enumerate(urls):
        if i:
            time.sleep(max(delay, 0.5))
        r = trace(u, session=session, delay=delay)
        r["fix"] = live_fix(r)
        rows.append(r)
        if progress:
            progress(i + 1, len(urls))
    return pd.DataFrame(rows, columns=cols)


def live_fix(r: dict) -> str:
    issue = r["issue"]
    if "loop" in issue:
        return "Break the loop: point the first URL at the live page"
    if "ends in" in issue:
        return "Redirect to a live page (or let it 404/410 if there is no replacement)" if r["redirects"] \
            else "Fix the page or remove links to it"
    if "chain" in issue:
        return f"Redirect straight to {r['final_url']} and update internal links"
    if "temporary" in issue:
        return "Use 301 if the move is permanent"
    if "https to http" in issue:
        return "Keep every hop on https"
    if r["redirects"]:
        return "Fine; update internal links to the final URL to skip the hop"
    return ""


# ---------------------------------------------------------------- output rules

def direct_rules(df: pd.DataFrame, source_col: str, target_col: str) -> pd.DataFrame:
    """source -> final target for every chain (loops have no final target and are left to you)."""
    cols = ["source", "target", "status"]
    if df.empty:
        return pd.DataFrame([], columns=cols)
    need = df[(df[target_col] != "") & df["issue"].str.contains("chain")]
    out = pd.DataFrame({"source": need[source_col], "target": need[target_col], "status": 301}, columns=cols)
    return out.drop_duplicates("source").reset_index(drop=True)


def _path(u: str) -> str:
    p = urlsplit(u)
    return (p.path or "/") + (f"?{p.query}" if p.query else "") if p.netloc else u


def htaccess(rules: pd.DataFrame) -> str:
    lines = ["# Direct redirects written by redirect-chain-fixer. Review before going live.",
             "# Apache mod_alias; put them above older rules for the same sources.", ""]
    for s, t in zip(rules["source"], rules["target"]):
        if "?" in _path(s):
            lines.append(f"# {s} has a query string: needs mod_rewrite with RewriteCond %{{QUERY_STRING}}")
            continue
        lines.append(f"Redirect 301 {_path(s)} {t}")
    return "\n".join(lines) + "\n"


def nginx(rules: pd.DataFrame) -> str:
    lines = ["# Direct redirects written by redirect-chain-fixer. Review before going live.",
             "# Put these inside the server { } block.", ""]
    for s, t in zip(rules["source"], rules["target"]):
        if "?" in _path(s):
            lines.append(f"# {s} has a query string: handle it with $arg_ checks")
            continue
        lines.append(f"location = {_path(s)} {{ return 301 {t}; }}")
    return "\n".join(lines) + "\n"


def summary(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["issue", "count"]
    if df.empty:
        return pd.DataFrame([], columns=cols)
    counts = {}
    for issue in df["issue"]:
        for part in filter(None, str(issue).split("; ")):
            name = part.split(" (")[0] if part.startswith("chain") else part
            counts[name] = counts.get(name, 0) + 1
    return pd.DataFrame(sorted(counts.items(), key=lambda kv: -kv[1]), columns=cols)
