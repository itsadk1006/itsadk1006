#!/usr/bin/env python3
"""Rewrite the LIVE TELEMETRY block in README.md using the GitHub GraphQL API.

Because the numbers are plain text inside the README (not an image served
through a cache), they are always as fresh as the last workflow run.
"""
import datetime as dt
import json
import os
import re
import urllib.request

LOGIN = os.environ.get("GH_LOGIN", "itsadk1006")
README = "README.md"
START, END = "<!--LIVE_STATS:START-->", "<!--LIVE_STATS:END-->"

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repos: repositories(first: 100, ownerAffiliations: [OWNER], isFork: false, privacy: PUBLIC) {
      totalCount
      nodes { stargazerCount }
    }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch(login):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={
            "Authorization": f"bearer {os.environ['GH_TOKEN']}",
            "Content-Type": "application/json",
            "User-Agent": "profile-readme-sync",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.load(resp)
        if "errors" in payload:
            raise RuntimeError(payload["errors"])
        return payload["data"]["user"]
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}")
        print(e.read().decode())
        raise SystemExit(1)


def streaks(days):
    counts = [d["contributionCount"] for d in days]
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    current = 0
    for i, c in enumerate(reversed(counts)):
        if c:
            current += 1
        elif i == 0:
            continue  # today isn't over yet, don't break the streak
        else:
            break
    return current, longest


def render(user, today):
    cal = user["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    current, longest = streaks(days)
    stars = sum(n["stargazerCount"] for n in user["repos"]["nodes"])

    rows = [
        ("contributions (1y)", f"{cal['totalContributions']}"),
        ("current streak", f"{current} day{'s' if current != 1 else ''}"),
        ("longest streak (1y)", f"{longest} day{'s' if longest != 1 else ''}"),
        ("public repos", f"{user['repos']['totalCount']}"),
        ("stars earned", f"{stars}"),
        ("followers", f"{user['followers']['totalCount']}"),
    ]

    width = 46
    title = f" LIVE TELEMETRY · {today} "
    lines = ["┌" + ("─[" + title + "]").ljust(width, "─") + "┐"]
    for label, value in rows:
        lines.append("│" + f" {label:<21}▸ {value}".ljust(width) + "│")
    lines.append("└" + "─" * width + "┘")
    return "```text\n" + "\n".join(lines) + "\n```"


def main():
    with open(README, encoding="utf-8") as f:
        text = f.read()

    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    if not pattern.search(text):
        raise SystemExit(f"Markers {START} / {END} not found in {README}")

    today = dt.datetime.now(dt.timezone.utc).strftime("%d %b %Y")
    block = render(fetch(LOGIN), today)
    new_text = pattern.sub(lambda _: f"{START}\n{block}\n{END}", text)

    if new_text != text:
        with open(README, "w", encoding="utf-8") as f:
            f.write(new_text)
        print("README updated.")
    else:
        print("No changes.")


if __name__ == "__main__":
    main()