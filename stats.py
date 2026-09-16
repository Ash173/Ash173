#!/usr/bin/env python3
"""
Fetch live GitHub numbers and write them to stats.json.

Needs a GitHub token. Easiest way, on any OS: put it in a file named .env
next to this script —

    GH_TOKEN=ghp_yourtokenhere

— then just run `python stats.py`. (.env is gitignored; never commit it.)

Or set it in your shell first:

    PowerShell   $env:GH_TOKEN = "ghp_xxx"
    cmd.exe      set GH_TOKEN=ghp_xxx
    bash/zsh     export GH_TOKEN=ghp_xxx

Zero third-party dependencies — standard library only.

Line-of-code counting is the expensive part, so per-repo results are cached in
cache/loc.json keyed by the repo's head commit SHA. A repo that hasn't moved
since the last run is skipped entirely, which makes the daily CI run cheap.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import config

HERE = Path(__file__).parent
CACHE_DIR = HERE / "cache"
CACHE_FILE = CACHE_DIR / "loc.json"
OUT_FILE = HERE / "stats.json"

API = "https://api.github.com/graphql"


def load_env_file(path: Path):
    """
    Minimal .env reader — no dependency, and it saves fighting with shell
    syntax differences between PowerShell, cmd and bash. Real environment
    variables always win over the file.
    """
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(HERE / ".env")

TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
USER = config.GITHUB_USER

MAX_PAGES = 200          # safety valve on any pagination loop


# ──────────────────────────────────────────────────────────────────
#  transport
# ──────────────────────────────────────────────────────────────────

def gql(query: str, variables: dict, attempt: int = 1):
    """POST a GraphQL query. Retries on transient failures and rate limits."""
    if not TOKEN:
        sys.exit(
            "No GitHub token found.\n\n"
            "Easiest fix — create a file called .env next to this script "
            "containing one line:\n\n"
            "    GH_TOKEN=ghp_yourtokenhere\n\n"
            "Or set it in your shell first:\n"
            '    PowerShell   $env:GH_TOKEN = "ghp_xxx"\n'
            "    cmd.exe      set GH_TOKEN=ghp_xxx\n"
            "    bash/zsh     export GH_TOKEN=ghp_xxx\n"
        )

    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        API,
        data=body,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": f"{USER}-profile-card",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code in (403, 429, 502, 503) and attempt <= 5:
            wait = 2 ** attempt
            print(f"  HTTP {e.code}; retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)
            return gql(query, variables, attempt + 1)
        raise
    except urllib.error.URLError:
        if attempt <= 5:
            wait = 2 ** attempt
            print(f"  network error; retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)
            return gql(query, variables, attempt + 1)
        raise

    if "errors" in payload:
        msg = "; ".join(e.get("message", "?") for e in payload["errors"])
        # A RATE_LIMITED error is worth waiting out; anything else is a real bug.
        if "RATE_LIMITED" in json.dumps(payload["errors"]) and attempt <= 5:
            print(f"  rate limited; sleeping 60s", file=sys.stderr)
            time.sleep(60)
            return gql(query, variables, attempt + 1)
        raise RuntimeError(f"GraphQL error: {msg}")

    return payload["data"]


# ──────────────────────────────────────────────────────────────────
#  queries
# ──────────────────────────────────────────────────────────────────

Q_USER = """
query($login: String!) {
  user(login: $login) {
    id
    login
    name
    createdAt
    followers { totalCount }
    following { totalCount }
    repositoriesContributedTo(
      first: 1,
      contributionTypes: [COMMIT, PULL_REQUEST, ISSUE, REPOSITORY, PULL_REQUEST_REVIEW]
    ) { totalCount }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
      contributionYears
    }
  }
}
"""

Q_REPOS = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    repositories(
      first: 100, after: $cursor,
      ownerAffiliations: OWNER, isFork: false,
      orderBy: {field: STARGAZERS, direction: DESC}
    ) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        name
        nameWithOwner
        isPrivate
        stargazerCount
        languages(first: 12, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
        defaultBranchRef { target { ... on Commit { oid } } }
      }
    }
  }
}
"""

Q_HISTORY = """
query($owner: String!, $name: String!, $authorId: ID!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef {
      target {
        ... on Commit {
          history(first: 100, after: $cursor, author: {id: $authorId}) {
            totalCount
            pageInfo { hasNextPage endCursor }
            nodes { additions deletions }
          }
        }
      }
    }
  }
}
"""

Q_YEAR = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { totalContributions }
    }
  }
}
"""


# ──────────────────────────────────────────────────────────────────
#  steps
# ──────────────────────────────────────────────────────────────────

def fetch_repos():
    """All owned, non-fork repos with stars, languages and head SHA."""
    repos, cursor = [], None
    for _ in range(MAX_PAGES):
        data = gql(Q_REPOS, {"login": USER, "cursor": cursor})["user"]["repositories"]
        repos.extend(data["nodes"])
        if not data["pageInfo"]["hasNextPage"]:
            return repos, data["totalCount"]
        cursor = data["pageInfo"]["endCursor"]
    return repos, len(repos)


def fetch_repo_loc(owner: str, name: str, author_id: str):
    """Additions/deletions/commits authored by the user on the default branch."""
    add = dele = commits = 0
    cursor = None
    for _ in range(MAX_PAGES):
        ref = gql(Q_HISTORY, {
            "owner": owner, "name": name, "authorId": author_id, "cursor": cursor,
        })["repository"]["defaultBranchRef"]

        if not ref:                       # empty repo
            return 0, 0, 0

        hist = ref["target"]["history"]
        commits = hist["totalCount"]
        for n in hist["nodes"]:
            add += n["additions"]
            dele += n["deletions"]

        if not hist["pageInfo"]["hasNextPage"]:
            break
        cursor = hist["pageInfo"]["endCursor"]

    return add, dele, commits


def fetch_loc(repos, author_id):
    """Sum LOC across repos, reusing cached values for unchanged repos."""
    CACHE_DIR.mkdir(exist_ok=True)
    cache = {}
    if CACHE_FILE.exists():
        try:
            cache = json.loads(CACHE_FILE.read_text())
        except json.JSONDecodeError:
            print("  cache corrupt, rebuilding", file=sys.stderr)

    total_add = total_del = total_commits = 0
    scanned = skipped = 0

    for repo in repos:
        slug = repo["nameWithOwner"]
        ref = repo.get("defaultBranchRef")
        if not ref:
            continue
        oid = ref["target"]["oid"]

        hit = cache.get(slug)
        if hit and hit.get("oid") == oid:
            skipped += 1
        else:
            owner, name = slug.split("/", 1)
            a, d, c = fetch_repo_loc(owner, name, author_id)
            cache[slug] = {"oid": oid, "additions": a, "deletions": d, "commits": c}
            scanned += 1
            print(f"  scanned {slug}: +{a} -{d} ({c} commits)")

        entry = cache[slug]
        total_add += entry["additions"]
        total_del += entry["deletions"]
        total_commits += entry["commits"]

    # Drop cache entries for repos that no longer exist.
    live = {r["nameWithOwner"] for r in repos}
    cache = {k: v for k, v in cache.items() if k in live}
    CACHE_FILE.write_text(json.dumps(cache, indent=2, sort_keys=True))

    print(f"  {scanned} repo(s) scanned, {skipped} cached")
    return total_add, total_del, total_commits


def fetch_contributions(years):
    """Total contributions across every year the account has been active."""
    total = 0
    for y in years:
        data = gql(Q_YEAR, {
            "login": USER,
            "from": f"{y}-01-01T00:00:00Z",
            "to": f"{y}-12-31T23:59:59Z",
        })
        total += data["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    return total


def top_languages(repos, limit=8):
    """Aggregate language bytes across repos, biggest first."""
    sizes, colours = {}, {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            lang = edge["node"]["name"]
            sizes[lang] = sizes.get(lang, 0) + edge["size"]
            colours[lang] = edge["node"]["color"] or "#8b949e"

    grand = sum(sizes.values()) or 1
    ranked = sorted(sizes.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [
        {"name": n, "bytes": b, "pct": round(100 * b / grand, 1), "color": colours[n]}
        for n, b in ranked
    ]


def main():
    print(f"Fetching stats for {USER} ...")

    user = gql(Q_USER, {"login": USER})["user"]
    author_id = user["id"]
    cc = user["contributionsCollection"]

    print("Fetching repositories ...")
    repos, repo_count = fetch_repos()
    print(f"  {repo_count} repo(s)")

    print("Counting lines of code ...")
    add, dele, commits = fetch_loc(repos, author_id)

    print("Fetching contribution history ...")
    contributions = fetch_contributions(cc["contributionYears"])

    langs = top_languages(repos)
    stars = sum(r["stargazerCount"] for r in repos)
    top = max(repos, key=lambda r: r["stargazerCount"], default=None)

    stats = {
        "login": user["login"],
        "name": user["name"],
        "repos": repo_count,
        "contributed": user["repositoriesContributedTo"]["totalCount"],
        "stars": stars,
        "followers": user["followers"]["totalCount"],
        "following": user["following"]["totalCount"],
        "commits": commits,
        "commits_this_year": cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
        "contributions_total": contributions,
        "loc_added": add,
        "loc_deleted": dele,
        "loc_net": add - dele,
        "top_repo": top["name"] if top else "—",
        "top_repo_stars": top["stargazerCount"] if top else 0,
        "languages": langs,
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }

    OUT_FILE.write_text(json.dumps(stats, indent=2))
    print(f"\nwrote {OUT_FILE.name}")
    for k in ("repos", "stars", "followers", "commits", "loc_net"):
        print(f"  {k:<12} {stats[k]:,}")


if __name__ == "__main__":
    main()
