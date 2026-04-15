"""Basic usage: connect, create issues, and manage your backlog.

Before running, copy .env.example to .env and fill in your credentials.
"""

from src import JiraClient

client = JiraClient()

# ── Verify connection ──────────────────────────────────────────────
me = client.get_myself()
print(f"Connected as: {me['displayName']} ({me['emailAddress']})")

# ── List projects ──────────────────────────────────────────────────
projects = client.get_projects()
for p in projects:
    print(f"  {p['key']}: {p['name']}")

# ── Create a user story ───────────────────────────────────────────
story = client.create_issue(
    project_key="HEALTH",
    summary="Patient portal: add medication history view",
    issue_type="Story",
    description=(
        "As a patient, I want to see my medication history "
        "so I can share it with my new provider.\n\n"
        "Acceptance criteria:\n"
        "- Display medication name, dosage, prescriber\n"
        "- Filter by date range\n"
        "- Export as PDF"
    ),
    priority="High",
    labels=["patient-portal", "q2-2026"],
)
print(f"Created story: {story['key']}")

# ── Create a bug ──────────────────────────────────────────────────
bug = client.create_issue(
    project_key="HEALTH",
    summary="Login timeout too short for SSO redirect",
    issue_type="Bug",
    description="Users on slow connections get logged out during SSO redirect.",
    priority="Critical",
    labels=["auth", "bug"],
)
print(f"Created bug: {bug['key']}")

# ── Update an issue ───────────────────────────────────────────────
client.update_issue(story["key"], summary="Patient portal: medication history view (MVP)")
client.add_labels(story["key"], ["mvp"])

# ── Transition to In Progress ─────────────────────────────────────
client.transition_issue(story["key"], "In Progress")

# ── Add a comment ─────────────────────────────────────────────────
client.add_comment(story["key"], "Discussed in sprint planning — targeting Sprint 14.")

# ── Link related issues ──────────────────────────────────────────
client.link_issues(bug["key"], story["key"], link_type="Relates")

# ── Read back the issue ──────────────────────────────────────────
issue = client.get_issue(story["key"])
print(f"Status: {issue['fields']['status']['name']}")
print(f"Labels: {issue['fields']['labels']}")
