"""Bulk operations — create multiple issues at once, useful for sprint planning."""

from src import JiraClient

client = JiraClient()

PROJECT = "HEALTH"

# ── Bulk create stories for a feature ─────────────────────────────
stories = [
    {
        "project": {"key": PROJECT},
        "issuetype": {"name": "Story"},
        "summary": "Design medication history UI mockups",
        "priority": {"name": "High"},
        "labels": ["patient-portal", "design"],
    },
    {
        "project": {"key": PROJECT},
        "issuetype": {"name": "Story"},
        "summary": "Implement medication history API endpoint",
        "priority": {"name": "High"},
        "labels": ["patient-portal", "backend"],
    },
    {
        "project": {"key": PROJECT},
        "issuetype": {"name": "Story"},
        "summary": "Build medication history frontend component",
        "priority": {"name": "Medium"},
        "labels": ["patient-portal", "frontend"],
    },
    {
        "project": {"key": PROJECT},
        "issuetype": {"name": "Story"},
        "summary": "Add PDF export for medication history",
        "priority": {"name": "Low"},
        "labels": ["patient-portal", "export"],
    },
]

result = client.bulk_create_issues(stories)

created = result.get("issues", [])
errors = result.get("errors", [])

print(f"Created {len(created)} issues:")
for issue in created:
    print(f"  {issue['key']}")

if errors:
    print(f"Errors: {len(errors)}")
    for err in errors:
        print(f"  {err}")
