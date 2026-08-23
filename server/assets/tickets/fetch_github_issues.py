import requests
import json
import time

REPOS = [
    "kubernetes/kubernetes",       # infrastructure/container orchestration
    "spring-projects/spring-boot", # enterprise Java framework
    "elastic/elasticsearch",       # search/database engine
    "microsoft/vscode",            # developer tooling
    "redis/redis",                 # in-memory database
    "prometheus/prometheus",       # monitoring/observability infrastructure
    "grafana/grafana",             # dashboards/data visualization
    "facebook/react",              # frontend framework
    "docker/compose",              # containerization tooling
    "nodejs/node",                 # runtime/language-level infrastructure
]

TICKETS_PER_REPO = 200  

all_tickets = []

for repo in REPOS:
    print(f"\n=== Fetching from {repo} ===")
    url = f"https://api.github.com/repos/{repo}/issues"
    repo_tickets = []
    page = 1

    while len(repo_tickets) < TICKETS_PER_REPO:
        params = {
            "state": "closed",
            "per_page": 100,
            "page": page
        }

        response = requests.get(url, params=params)

        if response.status_code != 200:
            print(f"Error fetching {repo}: {response.status_code} - {response.text}")
            break

        issues = response.json()

        if not issues:
            print(f"No more issues available for {repo}.")
            break

        for issue in issues:
            if "pull_request" in issue:
                continue  # skip PRs

            # Prefix ID with repo shortname to avoid ID collisions across repos
            repo_short = repo.split("/")[-1]
            repo_tickets.append({
                "id": f"{repo_short}-{issue['number']}",
                "title": issue["title"],
                "description": (issue["body"] or "No description provided.")[:500],
                "resolution": f"Closed via GitHub issue #{issue['number']} in {repo} (see linked PR/comments for fix details)",
                "source_repo": repo
            })

            if len(repo_tickets) >= TICKETS_PER_REPO:
                break

        print(f"  Page {page}: collected {len(repo_tickets)} tickets so far from {repo}...")
        page += 1
        time.sleep(1)  # be polite to GitHub's API

        if page > 5:  # safety cap per repo
            break

    all_tickets.extend(repo_tickets)
    print(f"Done with {repo}: {len(repo_tickets)} tickets collected.")

with open("github_tickets.json", "w") as f:
    json.dump(all_tickets, f, indent=2)

print(f"\nSaved {len(all_tickets)} total tickets across {len(REPOS)} repos to github_tickets.json")