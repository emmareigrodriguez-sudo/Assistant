# Jira Cloud API Integration

Python client for Jira Cloud REST API v3 and Agile API. Built for healthcare project management workflows.

## Setup

```bash
# Install dependencies
pip install -e ".[dev]"

# Configure credentials
cp .env.example .env
# Edit .env with your Jira Cloud credentials
```

### Getting your API token

1. Go to [https://id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click **Create API token**
3. Copy the token into `JIRA_API_TOKEN` in your `.env` file

## Quick start

```python
from src import JiraClient

client = JiraClient()

# Verify connection
me = client.get_myself()
print(f"Connected as {me['displayName']}")

# Create an issue
issue = client.create_issue(
    project_key="HEALTH",
    summary="Patient portal: medication history",
    issue_type="Story",
    priority="High",
    labels=["patient-portal"],
)

# Search with JQL
bugs = client.search_issues('project = HEALTH AND issuetype = Bug AND status != Done')

# Transition an issue
client.transition_issue("HEALTH-42", "In Progress")
```

## Features

| Area | Operations |
|------|-----------|
| **Issues** | Create, read, update, delete, transition, comment, assign, label, link |
| **Search** | JQL queries with auto-pagination |
| **Projects** | List and get project details |
| **Boards** | List boards by project |
| **Sprints** | List sprints, get sprint issues, backlog |
| **Epics** | List epics, get epic issues |
| **Users** | Search users, get current user |
| **Bulk** | Create multiple issues at once |
| **Webhooks** | Receive and handle Jira events in real-time |

## Examples

| File | Description |
|------|-------------|
| `examples/01_basic_usage.py` | Connect, create issues, update, transition |
| `examples/02_sprint_management.py` | Boards, sprints, backlog, epics |
| `examples/03_jql_reports.py` | JQL queries for PO dashboards |
| `examples/04_webhooks.py` | Real-time event listener |
| `examples/05_bulk_operations.py` | Bulk issue creation for sprint planning |

## Webhooks

To receive real-time events from Jira:

```python
from src import WebhookListener

listener = WebhookListener()

@listener.on("jira:issue_created")
def on_created(event):
    print(f"New issue: {event.issue_key}")

listener.start()  # Listens on port 5000
```

Register the webhook in Jira: **Settings → System → WebHooks** → point to `https://your-server/webhook/jira`.

## Tests

```bash
pytest -v
pytest --cov=src
```

## Security notes

- API tokens are loaded from environment variables, never hardcoded
- Webhook signatures are validated when `WEBHOOK_SECRET` is configured
- Logging is configured to avoid printing sensitive data (tokens, PHI)
- All HTTP communication uses HTTPS with retry logic
- No patient data (PHI) should be stored in Jira issue fields — use references/IDs only
