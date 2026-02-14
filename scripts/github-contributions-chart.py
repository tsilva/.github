#!/usr/bin/env python3
"""Generate interactive line charts of GitHub contributions, stars, and forks over time.

Requires: gh CLI (authenticated)
Usage: python scripts/github-contributions-chart.py [--username USERNAME] [--no-open]
"""

import argparse
import json
import subprocess
import sys
import tempfile
import webbrowser
from collections import defaultdict
from pathlib import Path

# --- GraphQL queries for contributions ---

GRAPHQL_QUERY_VIEWER = """
{
  viewer {
    login
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""

GRAPHQL_QUERY_USER = """
query($login: String!) {
  user(login: $login) {
    login
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""

# --- HTML template ---

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GitHub Dashboard — {login}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0d1117; color: #e6edf3; padding: 32px; }}
  h1 {{ font-size: 24px; font-weight: 600; margin-bottom: 24px; }}
  .chart-section {{ margin-bottom: 32px; }}
  .chart-section h2 {{ font-size: 16px; font-weight: 600; margin-bottom: 4px; }}
  .chart-section .subtitle {{ color: #8b949e; font-size: 13px; margin-bottom: 12px; }}
  .chart-container {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 24px; }}
  canvas {{ width: 100% !important; }}
  .repo-list {{ display: flex; flex-direction: column; gap: 0; }}
  .repo-row {{ display: flex; align-items: center; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #21262d; }}
  .repo-row:last-child {{ border-bottom: none; }}
  .repo-name {{ color: #58a6ff; text-decoration: none; font-size: 14px; font-weight: 500; }}
  .repo-name:hover {{ text-decoration: underline; }}
  .repo-stats {{ display: flex; gap: 16px; font-size: 13px; color: #8b949e; }}
  .repo-stats span {{ display: flex; align-items: center; gap: 4px; }}
  .star-icon {{ color: #e3b341; }}
  .fork-icon {{ color: #a371f7; }}
</style>
</head>
<body>

<h1>{login} — GitHub Dashboard</h1>

<div class="chart-section">
  <h2>Contributions</h2>
  <p class="subtitle">{total_contributions:,} contributions in the last year &middot; Daily counts with 7-day moving average</p>
  <div class="chart-container">
    <canvas id="contributionsChart"></canvas>
  </div>
</div>

<div class="chart-section">
  <h2>Stars</h2>
  <p class="subtitle">{total_stars:,} total stars across all repositories</p>
  <div class="chart-container">
    <canvas id="starsChart"></canvas>
  </div>
</div>

<div class="chart-section">
  <h2>Forks</h2>
  <p class="subtitle">{total_forks:,} total forks across all repositories</p>
  <div class="chart-container">
    <canvas id="forksChart"></canvas>
  </div>
</div>

<div class="chart-section">
  <h2>Repositories by Stars</h2>
  <p class="subtitle">{starred_repo_count} repositories with stars</p>
  <div class="chart-container repo-list">
    {repos_html}
  </div>
</div>

<script>
// --- Chart defaults ---
const gridColor = '#21262d';
const tickColor = '#8b949e';
const tooltipStyle = {{
  backgroundColor: '#161b22',
  borderColor: '#30363d',
  borderWidth: 1,
  titleColor: '#e6edf3',
  bodyColor: '#e6edf3',
}};

function timeScaleOpts(unit) {{
  return {{
    type: 'time',
    time: {{ unit: unit, tooltipFormat: 'MMM d, yyyy' }},
    grid: {{ color: gridColor }},
    ticks: {{ color: tickColor }},
  }};
}}

function yScaleOpts() {{
  return {{
    beginAtZero: true,
    grid: {{ color: gridColor }},
    ticks: {{ color: tickColor }},
  }};
}}

function ma(data, window) {{
  return data.map((_, i) => {{
    const start = Math.max(0, i - window + 1);
    const slice = data.slice(start, i + 1);
    return +(slice.reduce((a, b) => a + b, 0) / slice.length).toFixed(1);
  }});
}}

// --- Contributions chart ---
const contribRaw = {contributions_json};
const contribDates = contribRaw.map(d => d.date);
const contribCounts = contribRaw.map(d => d.c);
const contribMa7 = ma(contribCounts, 7);

new Chart(document.getElementById('contributionsChart'), {{
  type: 'line',
  data: {{
    labels: contribDates,
    datasets: [
      {{
        label: 'Daily contributions',
        data: contribCounts,
        borderColor: '#39d353',
        backgroundColor: 'rgba(57, 211, 83, 0.08)',
        borderWidth: 1,
        pointRadius: 0,
        fill: true,
        tension: 0,
      }},
      {{
        label: '7-day average',
        data: contribMa7,
        borderColor: '#f78166',
        borderWidth: 2,
        pointRadius: 0,
        fill: false,
        tension: 0.3,
      }}
    ]
  }},
  options: {{
    responsive: true,
    interaction: {{ mode: 'index', intersect: false }},
    scales: {{ x: timeScaleOpts('month'), y: yScaleOpts() }},
    plugins: {{ legend: {{ labels: {{ color: '#e6edf3' }} }}, tooltip: tooltipStyle }},
  }}
}});

// --- Stars chart ---
const starsRaw = {stars_json};

new Chart(document.getElementById('starsChart'), {{
  type: 'line',
  data: {{
    labels: starsRaw.map(d => d.date),
    datasets: [{{
      label: 'Cumulative stars',
      data: starsRaw.map(d => d.total),
      borderColor: '#e3b341',
      backgroundColor: 'rgba(227, 179, 65, 0.08)',
      borderWidth: 2,
      pointRadius: 0,
      fill: true,
      tension: 0.2,
    }}]
  }},
  options: {{
    responsive: true,
    interaction: {{ mode: 'index', intersect: false }},
    scales: {{ x: timeScaleOpts(starsRaw.length > 365 ? 'quarter' : 'month'), y: yScaleOpts() }},
    plugins: {{ legend: {{ labels: {{ color: '#e6edf3' }} }}, tooltip: tooltipStyle }},
  }}
}});

// --- Forks chart ---
const forksRaw = {forks_json};

new Chart(document.getElementById('forksChart'), {{
  type: 'line',
  data: {{
    labels: forksRaw.map(d => d.date),
    datasets: [{{
      label: 'Cumulative forks',
      data: forksRaw.map(d => d.total),
      borderColor: '#a371f7',
      backgroundColor: 'rgba(163, 113, 247, 0.08)',
      borderWidth: 2,
      pointRadius: 0,
      fill: true,
      tension: 0.2,
    }}]
  }},
  options: {{
    responsive: true,
    interaction: {{ mode: 'index', intersect: false }},
    scales: {{ x: timeScaleOpts(forksRaw.length > 365 ? 'quarter' : 'month'), y: yScaleOpts() }},
    plugins: {{ legend: {{ labels: {{ color: '#e6edf3' }} }}, tooltip: tooltipStyle }},
  }}
}});
</script>
</body>
</html>
"""


def gh_api(endpoint: str, extra_args: list[str] | None = None) -> str:
    """Call gh api and return stdout. Exits on failure."""
    cmd = ["gh", "api", "--paginate", endpoint]
    if extra_args:
        cmd.extend(extra_args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: gh api {endpoint}\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def gh_api_json(endpoint: str, extra_args: list[str] | None = None) -> list | dict:
    """Call gh api --paginate and parse JSON. Handles paginated array concatenation."""
    raw = gh_api(endpoint, extra_args)
    # --paginate concatenates JSON arrays as separate objects, join them
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # paginated arrays come as ][, e.g. [{...}][{...}]
        fixed = "[" + raw.replace("][", ",") + "]"
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            # Multiple top-level arrays — flatten
            parts = []
            for chunk in raw.split("\n"):
                chunk = chunk.strip()
                if chunk:
                    parts.extend(json.loads(chunk))
            return parts


def fetch_contributions(username: str | None = None) -> tuple[str, int, list[dict]]:
    """Fetch contribution calendar via GraphQL. Returns (login, total, daily_data)."""
    cmd = ["gh", "api", "graphql"]
    if username:
        cmd += ["-f", f"query={GRAPHQL_QUERY_USER}", "-f", f"login={username}"]
    else:
        cmd += ["-f", f"query={GRAPHQL_QUERY_VIEWER}"]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: contributions query failed\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    resp = json.loads(result.stdout)
    user = resp["data"]["user"] if username else resp["data"]["viewer"]
    login = user["login"]
    calendar = user["contributionsCollection"]["contributionCalendar"]
    total = calendar["totalContributions"]

    daily = []
    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            daily.append({"date": day["date"], "c": day["contributionCount"]})

    return login, total, daily


def fetch_repos(login: str) -> list[dict]:
    """Fetch all owned, non-fork repos with their star/fork counts."""
    repos = gh_api_json(f"/users/{login}/repos?type=owner&per_page=100")
    return [
        {"name": r["full_name"], "stars": r["stargazers_count"], "forks": r["forks_count"]}
        for r in repos
        if not r["fork"]
    ]


def fetch_star_dates(repo_name: str) -> list[str]:
    """Fetch starred_at dates for a repo using the star timestamps API."""
    data = gh_api_json(
        f"/repos/{repo_name}/stargazers?per_page=100",
        ["-H", "Accept: application/vnd.github.star+json"],
    )
    return [s["starred_at"][:10] for s in data if "starred_at" in s]


def fetch_fork_dates(repo_name: str) -> list[str]:
    """Fetch created_at dates for all forks of a repo."""
    data = gh_api_json(f"/repos/{repo_name}/forks?per_page=100")
    return [f["created_at"][:10] for f in data if "created_at" in f]


def build_cumulative(dates: list[str]) -> list[dict]:
    """Build a cumulative time series from a list of date strings."""
    if not dates:
        return []
    counts = defaultdict(int)
    for d in dates:
        counts[d] += 1
    sorted_dates = sorted(counts.keys())
    cumulative = []
    total = 0
    for d in sorted_dates:
        total += counts[d]
        cumulative.append({"date": d, "total": total})
    return cumulative


def main():
    parser = argparse.ArgumentParser(description="GitHub dashboard: contributions, stars, and forks")
    parser.add_argument("--username", "-u", help="GitHub username (default: authenticated user)")
    parser.add_argument("--no-open", action="store_true", help="Don't open in browser, just print the path")
    parser.add_argument("--output", "-o", help="Save HTML to this path instead of a temp file")
    args = parser.parse_args()

    # Contributions
    print("Fetching contributions...")
    login, total_contributions, daily = fetch_contributions(args.username)
    print(f"  {login}: {total_contributions:,} contributions in the last year")

    # Repos
    print("Fetching repositories...")
    repos = fetch_repos(login)
    print(f"  {len(repos)} owned repos")

    # Stars
    starred_repos = [r for r in repos if r["stars"] > 0]
    all_star_dates = []
    if starred_repos:
        print(f"Fetching star history ({len(starred_repos)} repos with stars)...")
        for i, r in enumerate(starred_repos, 1):
            print(f"  [{i}/{len(starred_repos)}] {r['name']} ({r['stars']} stars)")
            all_star_dates.extend(fetch_star_dates(r["name"]))

    total_stars = len(all_star_dates)
    stars_cumulative = build_cumulative(all_star_dates)
    print(f"  {total_stars:,} total stars")

    # Forks
    forked_repos = [r for r in repos if r["forks"] > 0]
    all_fork_dates = []
    if forked_repos:
        print(f"Fetching fork history ({len(forked_repos)} repos with forks)...")
        for i, r in enumerate(forked_repos, 1):
            print(f"  [{i}/{len(forked_repos)}] {r['name']} ({r['forks']} forks)")
            all_fork_dates.extend(fetch_fork_dates(r["name"]))

    total_forks = len(all_fork_dates)
    forks_cumulative = build_cumulative(all_fork_dates)
    print(f"  {total_forks:,} total forks")

    # Build repo list HTML (sorted by stars+forks descending, only repos with stars)
    starred_repos_sorted = sorted(starred_repos, key=lambda r: r["stars"] + r["forks"], reverse=True)
    repo_rows = []
    for r in starred_repos_sorted:
        name = r["name"]
        short = name.split("/", 1)[1] if "/" in name else name
        row = (
            f'<div class="repo-row">'
            f'<a class="repo-name" href="https://github.com/{name}" target="_blank">{short}</a>'
            f'<div class="repo-stats">'
            f'<span><span class="star-icon">&#9733;</span> {r["stars"]}</span>'
            f'<span><span class="fork-icon">&#9707;</span> {r["forks"]}</span>'
            f'</div></div>'
        )
        repo_rows.append(row)
    repos_html = "\n    ".join(repo_rows)

    # Generate HTML
    html = HTML_TEMPLATE.format(
        login=login,
        total_contributions=total_contributions,
        total_stars=total_stars,
        total_forks=total_forks,
        starred_repo_count=len(starred_repos_sorted),
        repos_html=repos_html,
        contributions_json=json.dumps(daily),
        stars_json=json.dumps(stars_cumulative),
        forks_json=json.dumps(forks_cumulative),
    )

    if args.output:
        out = Path(args.output)
    else:
        out = Path(tempfile.mktemp(suffix=".html", prefix="gh-dashboard-"))
    out.write_text(html)

    print(f"\nChart: {out}")

    if not args.no_open:
        webbrowser.open(f"file://{out.resolve()}")


if __name__ == "__main__":
    main()
