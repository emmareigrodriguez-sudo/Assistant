"""JQL queries and reporting — useful for PO dashboards and standups."""

from collections import Counter

from src import JiraClient

client = JiraClient()

PROJECT = "HEALTH"

# ── Open bugs by priority ─────────────────────────────────────────
bugs = client.search_issues(
    jql=f'project = {PROJECT} AND issuetype = Bug AND status != Done',
    fields=["summary", "priority", "assignee", "created"],
    max_results=200,
)

print(f"Open bugs: {len(bugs)}")
by_priority = Counter(b["fields"]["priority"]["name"] for b in bugs)
for priority, count in by_priority.most_common():
    print(f"  {priority}: {count}")

# ── Unassigned issues ─────────────────────────────────────────────
unassigned = client.search_issues(
    jql=f'project = {PROJECT} AND assignee is EMPTY AND status != Done',
    max_results=100,
)
print(f"\nUnassigned issues: {len(unassigned)}")
for issue in unassigned[:10]:
    print(f"  {issue['key']}: {issue['fields']['summary']}")

# ── Recently updated (last 24h) ───────────────────────────────────
recent = client.search_issues(
    jql=f'project = {PROJECT} AND updated >= -1d ORDER BY updated DESC',
    fields=["summary", "status", "updated"],
    max_results=20,
)
print(f"\nUpdated in last 24h: {len(recent)}")
for issue in recent:
    status = issue["fields"]["status"]["name"]
    print(f"  {issue['key']} [{status}]: {issue['fields']['summary']}")

# ── Stories without estimates ──────────────────────────────────────
no_estimate = client.search_issues(
    jql=(
        f'project = {PROJECT} AND issuetype = Story '
        f'AND (storyPoints is EMPTY OR storyPoints = 0) '
        f'AND status != Done'
    ),
    fields=["summary", "status"],
    max_results=50,
)
print(f"\nStories without estimates: {len(no_estimate)}")

# ── Blocked issues ────────────────────────────────────────────────
blocked = client.search_issues(
    jql=f'project = {PROJECT} AND status = "Blocked"',
    fields=["summary", "assignee", "priority"],
    max_results=50,
)
print(f"\nBlocked issues: {len(blocked)}")
for issue in blocked:
    assignee = issue["fields"].get("assignee")
    name = assignee["displayName"] if assignee else "Unassigned"
    print(f"  {issue['key']} ({name}): {issue['fields']['summary']}")

# ── Sprint completion rate (last 3 closed sprints) ────────────────
boards = client.get_boards(project_key=PROJECT)
if boards:
    closed_sprints = client.get_sprints(boards[0]["id"], state="closed")
    for sprint in closed_sprints[-3:]:
        issues = client.get_sprint_issues(sprint["id"])
        total = len(issues)
        done = sum(1 for i in issues if i["fields"]["status"]["name"] == "Done")
        rate = (done / total * 100) if total else 0
        print(f"\n  {sprint['name']}: {done}/{total} completed ({rate:.0f}%)")
