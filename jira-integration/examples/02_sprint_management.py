"""Sprint and board management: view sprints, backlog, and velocity data."""

from src import JiraClient

client = JiraClient()

PROJECT = "HEALTH"

# ── Find the board ─────────────────────────────────────────────────
boards = client.get_boards(project_key=PROJECT)
board = boards[0]
print(f"Board: {board['name']} (id: {board['id']})")

# ── Active sprint ──────────────────────────────────────────────────
active_sprints = client.get_sprints(board["id"], state="active")
if active_sprints:
    sprint = active_sprints[0]
    print(f"\nActive sprint: {sprint['name']}")
    print(f"  Start: {sprint.get('startDate', 'N/A')}")
    print(f"  End:   {sprint.get('endDate', 'N/A')}")

    issues = client.get_sprint_issues(sprint["id"])
    print(f"  Issues: {len(issues)}")

    # Group by status
    by_status: dict[str, list] = {}
    for issue in issues:
        status = issue["fields"]["status"]["name"]
        by_status.setdefault(status, []).append(issue)

    for status, items in by_status.items():
        print(f"    {status}: {len(items)}")
        for item in items:
            print(f"      - {item['key']}: {item['fields']['summary']}")

# ── Backlog ────────────────────────────────────────────────────────
backlog = client.get_backlog(board["id"])
print(f"\nBacklog items: {len(backlog)}")
for item in backlog[:5]:
    print(f"  {item['key']}: {item['fields']['summary']}")

# ── Future sprints ─────────────────────────────────────────────────
future = client.get_sprints(board["id"], state="future")
print(f"\nPlanned sprints: {len(future)}")
for s in future:
    print(f"  {s['name']}")

# ── Epics overview ─────────────────────────────────────────────────
epics = client.get_epics(board["id"])
print(f"\nEpics: {len(epics)}")
for epic in epics:
    epic_issues = client.get_epic_issues(epic["id"])
    done = sum(1 for i in epic_issues if i["fields"]["status"]["name"] == "Done")
    print(f"  {epic['name']}: {done}/{len(epic_issues)} done")
