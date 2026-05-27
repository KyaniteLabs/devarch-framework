"""Fetch repo metadata from GitHub API for all repos (no cloning needed)."""

import json
import os
import subprocess
import sys
from pathlib import Path


_DEFAULT_OWNER = os.environ.get("ARCHAEOLOGY_GITHUB_OWNER", "")


def _gh(*args):
    """Run a gh command and return stdout."""
    result = subprocess.run(["gh"] + list(args), capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _gh_api(endpoint, jq_filter=None):
    """Run a gh api call and return parsed output."""
    cmd = ["gh", "api", endpoint]
    if jq_filter:
        cmd.extend(["--jq", jq_filter])
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _fetch_all_contributors(owner, repo_name):
    """Fetch all contributors with pagination."""
    contributors = {}
    page = 1
    per_page = 100

    while True:
        contrib_raw = _gh_api(
            f"repos/{owner}/{repo_name}/contributors?per_page={per_page}&page={page}",
            ".[] | .login + \":\" + (.contributions|tostring)"
        )
        if not contrib_raw:
            break

        page_contributors = {}
        for line in contrib_raw.split("\n"):
            if ":" in line:
                login, count = line.split(":", 1)
                try:
                    c = int(count)
                    page_contributors[login] = c
                except ValueError:
                    pass

        if not page_contributors:
            break

        contributors.update(page_contributors)

        # If we got fewer than per_page results, we're done
        if len(page_contributors) < per_page:
            break

        page += 1

    return contributors


def fetch_all_repos(owner=_DEFAULT_OWNER, limit=None):
    """Fetch all repos with commit counts, languages, and authors.

    Args:
        owner: GitHub username or organization.
        limit: Maximum number of repos to fetch (None for all).
    """
    # Use a high limit to get all repos (gh repo list handles pagination internally)
    repo_limit = limit if limit else 10000
    raw = _gh("repo", "list", owner, "--limit", str(repo_limit),
              "--json", "name,isFork,primaryLanguage,createdAt,updatedAt,description,diskUsage")
    if not raw:
        print("Failed to fetch repo list from GitHub", file=sys.stderr)
        return []

    try:
        repo_list = json.loads(raw)
    except json.JSONDecodeError:
        print("Failed to parse repo list", file=sys.stderr)
        return []

    results = []
    total = len(repo_list)
    for i, repo in enumerate(repo_list):
        name = repo["name"]
        is_fork = repo.get("isFork", False)

        # Skip forks (awesome-mcp-servers, apex-vault etc)
        if is_fork:
            print(f"  [{i+1}/{total}] {name}... SKIP (fork)", flush=True)
            continue

        print(f"  [{i+1}/{total}] {name}...", end=" ", flush=True)

        # Get contributors with pagination
        authors = _fetch_all_contributors(owner, name)
        total_commits = sum(authors.values())

        # Get languages
        lang_raw = _gh_api(f"repos/{owner}/{name}/languages",
                           "to_entries | .[] | .key + \":\" + (.value|tostring)")
        languages = {}
        if lang_raw:
            for line in lang_raw.split("\n"):
                if ":" in line:
                    lang, bytes_str = line.split(":", 1)
                    try:
                        languages[lang] = int(bytes_str)
                    except ValueError:
                        pass

        # Skip repos with zero commits
        if total_commits == 0:
            print("SKIP (0 commits)", flush=True)
            continue

        lang_obj = repo.get("primaryLanguage")
        lang_name = lang_obj.get("name") if lang_obj else None

        results.append({
            "name": name,
            "language": lang_name,
            "created": repo.get("createdAt", "")[:10],
            "updated": repo.get("updatedAt", "")[:10],
            "description": repo.get("description", ""),
            "size_kb": repo.get("diskUsage", 0),
            "total_commits": total_commits,
            "authors": authors,
            "languages": languages,
        })
        print(f"{total_commits} commits, {len(authors)} authors", flush=True)

    return results


def save_github_data(output_path, owner=_DEFAULT_OWNER):
    """Fetch all repo data and save to JSON."""
    repos = fetch_all_repos(owner=owner)
    output = {
        "owner": owner,
        "total_repos": len(repos),
        "total_commits": sum(r["total_commits"] for r in repos),
        "repos": repos,
    }
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved {len(repos)} repos to {path}")
    return output
