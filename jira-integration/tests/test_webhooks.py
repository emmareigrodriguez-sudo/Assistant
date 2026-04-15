"""Tests for the webhook listener."""

import json

import pytest

from src.config import JiraConfig
from src.webhooks import WebhookEvent, WebhookListener


@pytest.fixture
def config():
    return JiraConfig(
        jira_base_url="https://test.atlassian.net",
        jira_user_email="test@example.com",
        jira_api_token="fake-token",
        webhook_secret="",
    )


@pytest.fixture
def listener(config):
    return WebhookListener(config)


@pytest.fixture
def flask_client(listener):
    listener.app.config["TESTING"] = True
    return listener.app.test_client()


# ── WebhookEvent parsing ──────────────────────────────────────────


class TestWebhookEvent:
    def test_parses_issue_created(self):
        payload = {
            "webhookEvent": "jira:issue_created",
            "timestamp": 1700000000,
            "issue": {
                "key": "PROJ-1",
                "fields": {"project": {"key": "PROJ"}},
            },
            "user": {"emailAddress": "dev@company.com"},
        }

        event = WebhookEvent.from_payload(payload)
        assert event.event_type == "jira:issue_created"
        assert event.issue_key == "PROJ-1"
        assert event.project_key == "PROJ"
        assert event.user_email == "dev@company.com"

    def test_parses_issue_updated_with_changelog(self):
        payload = {
            "webhookEvent": "jira:issue_updated",
            "timestamp": 1700000000,
            "issue": {"key": "PROJ-2", "fields": {"project": {"key": "PROJ"}}},
            "user": {"emailAddress": "pm@company.com"},
            "changelog": {
                "items": [
                    {
                        "field": "status",
                        "fromString": "To Do",
                        "toString": "In Progress",
                    }
                ]
            },
        }

        event = WebhookEvent.from_payload(payload)
        assert len(event.changelog) == 1
        assert event.changelog[0]["field"] == "status"

    def test_handles_missing_fields(self):
        event = WebhookEvent.from_payload({"webhookEvent": "unknown"})
        assert event.event_type == "unknown"
        assert event.issue_key is None
        assert event.changelog == []


# ── Webhook endpoint ──────────────────────────────────────────────


class TestWebhookEndpoint:
    def test_health_check(self, flask_client):
        resp = flask_client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "healthy"

    def test_receives_event(self, listener, flask_client):
        received = []

        @listener.on("jira:issue_created")
        def handler(event):
            received.append(event)

        resp = flask_client.post(
            "/webhook/jira",
            data=json.dumps({
                "webhookEvent": "jira:issue_created",
                "timestamp": 1700000000,
                "issue": {"key": "PROJ-1", "fields": {"project": {"key": "PROJ"}}},
                "user": {"emailAddress": "test@co.com"},
            }),
            content_type="application/json",
        )

        assert resp.status_code == 200
        assert len(received) == 1
        assert received[0].issue_key == "PROJ-1"

    def test_wildcard_handler(self, listener, flask_client):
        received = []

        @listener.on("*")
        def catch_all(event):
            received.append(event.event_type)

        flask_client.post(
            "/webhook/jira",
            data=json.dumps({"webhookEvent": "jira:issue_deleted", "timestamp": 0}),
            content_type="application/json",
        )

        assert "jira:issue_deleted" in received

    def test_rejects_invalid_json(self, flask_client):
        resp = flask_client.post(
            "/webhook/jira",
            data="not json",
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_handler_error_doesnt_crash(self, listener, flask_client):
        @listener.on("jira:issue_created")
        def bad_handler(event):
            raise RuntimeError("oops")

        resp = flask_client.post(
            "/webhook/jira",
            data=json.dumps({"webhookEvent": "jira:issue_created", "timestamp": 0}),
            content_type="application/json",
        )
        # Should still return 200 — handler errors are logged, not propagated
        assert resp.status_code == 200
