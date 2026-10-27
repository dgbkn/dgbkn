#!/usr/bin/env python3
"""Generate the SVG stats cards used by the profile README.

The cards are written to assets/stats/ and are committed to the repository, so the
README does not depend on any third-party widget service. Requires the GitHub CLI
(`gh`) to be installed and authenticated.

Usage: python3 scripts/generate_stats.py
"""
import datetime
import html
import json
import os
import subprocess

USER = "dgbkn"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "assets", "stats")

BG, BORDER = "#0d1117", "#30363d"
TEXT, MUTED, ACCENT = "#e6edf3", "#8b949e", "#58a6ff"
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"


def gql(query, **variables):
    cmd = ["gh", "api", "graphql", "-f", "query=" + query]
    for key, value in variables.items():
        if value is None:
            continue
        cmd += ["-F" if isinstance(value, (int, bool)) else "-f", f"{key}={value}"]
    return json.loads(subprocess.check_output(cmd))["data"]


def fetch():
    main = gql(
        """query($login:String!){ user(login:$login){
          followers{totalCount} following{totalCount} createdAt
          contributionsCollection{
            totalCommitContributions totalPullRequestContributions totalIssueContributions
            contributionCalendar{ totalContributions weeks{ contributionDays{ date contributionCount } } }
          } } }""",
        login=USER,
    )["user"]

    repos, cursor = [], None
    while True:
        page = gql(
            """query($login:String!,$cursor:String){ user(login:$login){
              repositories(first:100, after:$cursor, ownerAffiliations:OWNER, isFork:false){
                pageInfo{hasNextPage endCursor}
                nodes{ isPrivate stargazerCount
                  languages(first:10, orderBy:{field:SIZE, direction:DESC}){ edges{ size node{ name color } } } } } } }""",
            login=USER,
            cursor=cursor,
        )["user"]["repositories"]
        repos += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
    return main, repos


def streaks(days):
    days = sorted(days, key=lambda d: d["date"])
    longest = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] > 0 else 0
        longest = max(longest, run)
    today = datetime.date.today().isoformat()
    current = 0
    for d in reversed(days):
        if d["date"] > today:
            continue
        if d["contributionCount"] > 0:
            current += 1
        elif d["date"] == today:
            continue  # today may not have contributions yet
        else:
            break
    return current, longest


def card(width, height, title, body):
    updated = datetime.date.today().isoformat()
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">
  <title>{html.escape(title)}</title>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" fill="{BG}" stroke="{BORDER}"/>
  <text x="24" y="36" fill="{TEXT}" font-family="{FONT}" font-size="17" font-weight="600">{html.escape(title)}</text>
  <rect x="24" y="46" width="32" height="3" rx="1.5" fill="{ACCENT}"/>
{body}
  <text x="{width - 20}" y="{height - 14}" fill="{MUTED}" font-family="{FONT}" font-size="10" text-anchor="end">Updated {updated}</text>
</svg>
"""


def overview(main, repos):
    public = [r for r in repos if not r["isPrivate"]]
    stars = sum(r["stargazerCount"] for r in public)
    languages_used = {e["node"]["name"] for r in repos for e in r["languages"]["edges"]}
    items = [
        (len(public), "Public repositories"),
        (stars, "Stars earned"),
        (main["followers"]["totalCount"], "Followers"),
        (main["following"]["totalCount"], "Following"),
        (len(languages_used), "Languages used"),
        (main["createdAt"][:4], "On GitHub since"),
    ]
    body = []
    for i, (value, label) in enumerate(items):
        x = 24 + (i % 2) * 206
        y = 92 + (i // 2) * 48
        body.append(f'  <text x="{x}" y="{y}" fill="{ACCENT}" font-family="{FONT}" font-size="22" font-weight="700">{value:,}</text>' if isinstance(value, int) else f'  <text x="{x}" y="{y}" fill="{ACCENT}" font-family="{FONT}" font-size="22" font-weight="700">{value}</text>')
        body.append(f'  <text x="{x}" y="{y + 17}" fill="{MUTED}" font-family="{FONT}" font-size="12">{html.escape(label)}</text>')
    return card(440, 245, "GitHub Overview", "\n".join(body))


def languages(repos):
    totals, colors = {}, {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            totals[name] = totals.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or "#8b949e"
    grand = sum(totals.values()) or 1
    top = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:6]
    other = grand - sum(v for _, v in top)

    body, x, bar_w = [], 24.0, 392
    body.append('  <clipPath id="bar"><rect x="24" y="64" width="392" height="10" rx="5"/></clipPath>')
    body.append('  <g clip-path="url(#bar)">')
    segments = [(n, v, colors[n]) for n, v in top]
    if other > 0:
        segments.append(("Other", other, "#484f58"))
    for name, value, color in segments:
        w = bar_w * value / grand
        body.append(f'    <rect x="{x:.2f}" y="64" width="{w:.2f}" height="10" fill="{color}"/>')
        x += w
    body.append("  </g>")
    for i, (name, value) in enumerate(top):
        cx = 24 + (i % 2) * 206
        cy = 108 + (i // 2) * 36
        pct = 100 * value / grand
        body.append(f'  <circle cx="{cx + 5}" cy="{cy - 4}" r="5" fill="{colors[name]}"/>')
        body.append(f'  <text x="{cx + 18}" y="{cy}" fill="{TEXT}" font-family="{FONT}" font-size="13">{html.escape(name)}</text>')
        body.append(f'  <text x="{cx + 18}" y="{cy + 15}" fill="{MUTED}" font-family="{FONT}" font-size="11">{pct:.1f}%</text>')
    return card(440, 245, "Top Languages", "\n".join(body))


def streak(main):
    cal = main["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    current, longest = streaks(days)
    blocks = [
        (f"{cal['totalContributions']:,}", "Contributions in the last 12 months"),
        (f"{current}", "Current streak (days)"),
        (f"{longest}", "Longest streak (days)"),
    ]
    width = 900
    body = []
    for i, (value, label) in enumerate(blocks):
        cx = 150 + i * 300
        body.append(f'  <text x="{cx}" y="96" fill="{ACCENT}" font-family="{FONT}" font-size="30" font-weight="700" text-anchor="middle">{value}</text>')
        body.append(f'  <text x="{cx}" y="120" fill="{MUTED}" font-family="{FONT}" font-size="12" text-anchor="middle">{html.escape(label)}</text>')
        if i:
            body.append(f'  <rect x="{cx - 150}" y="68" width="1" height="62" fill="{BORDER}"/>')
    return card(width, 150, "Contribution Activity", "\n".join(body))


def main():
    os.makedirs(OUT, exist_ok=True)
    data, repos = fetch()
    outputs = {
        "overview.svg": overview(data, repos),
        "languages.svg": languages(repos),
        "streak.svg": streak(data),
    }
    for name, svg in outputs.items():
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
            fh.write(svg)
        print("wrote", name)


if __name__ == "__main__":
    main()
