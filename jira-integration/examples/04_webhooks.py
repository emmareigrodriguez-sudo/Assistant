"""Webhook listener — receive real-time events from Jira Cloud.

Setup in Jira:
  1. Go to Settings → System → WebHooks
  2. Create a webhook pointing to: https://your-server/webhook/jira
  3. Select events: issue created, updated, deleted, comment created
  4. (Optional) Set a secret and configure WEBHOOK_SECRET in .env
"""

from src import JiraConfig, WebhookListener
from src.webhooks import WebhookEvent

config = JiraConfig()
listener = WebhookListener(config)


@listener.on(WebhookListener.ISSUE_CREATED)
def on_issue_created(event: WebhookEvent):
    print(f"New issue: {event.issue_key} in {event.project_key}")
    # Example: auto-assign to triage, notify Slack, etc.


@listener.on(WebhookListener.ISSUE_UPDATED)
def on_issue_updated(event: WebhookEvent):
    for change in event.changelog:
        field = change.get("field")
        from_val = change.get("fromString", "")
        to_val = change.get("toString", "")
        print(f"  {event.issue_key}: {field} changed from '{from_val}' to '{to_val}'")

    # Detect status transitions
    status_changes = [c for c in event.changelog if c.get("field") == "status"]
    for change in status_changes:
        if change.get("toString") == "Done":
            print(f"  ✓ {event.issue_key} completed by {event.user_email}")


@listener.on(WebhookListener.COMMENT_CREATED)
def on_comment(event: WebhookEvent):
    print(f"New comment on {event.issue_key} by {event.user_email}")


@listener.on("*")
def log_all_events(event: WebhookEvent):
    """Catch-all handler for audit logging."""
    print(f"[AUDIT] {event.event_type} | {event.issue_key} | {event.user_email}")


if __name__ == "__main__":
    print("Starting Jira webhook listener...")
    print("Health check: http://localhost:5000/health")
    print("Webhook URL:  http://localhost:5000/webhook/jira")
    listener.start(debug=True)
