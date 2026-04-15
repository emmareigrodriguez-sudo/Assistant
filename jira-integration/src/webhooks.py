"""Webhook listener for Jira Cloud events.

Receives and validates incoming webhook payloads from Jira Cloud.
Register webhooks at: Jira Settings → System → WebHooks.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from flask import Flask, Request, abort, jsonify, request

from .config import JiraConfig

logger = logging.getLogger("jira_integration.webhooks")

# Type alias for event handlers
EventHandler = Callable[[dict], None]


@dataclass
class WebhookEvent:
    """Parsed webhook event from Jira."""

    event_type: str  # e.g. "jira:issue_created"
    timestamp: int
    issue_key: str | None = None
    project_key: str | None = None
    user_email: str | None = None
    changelog: list[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_payload(cls, payload: dict) -> WebhookEvent:
        event_type = payload.get("webhookEvent", "unknown")
        issue = payload.get("issue", {})
        user = payload.get("user", {})
        changelog = payload.get("changelog", {}).get("items", [])

        return cls(
            event_type=event_type,
            timestamp=payload.get("timestamp", 0),
            issue_key=issue.get("key"),
            project_key=issue.get("fields", {}).get("project", {}).get("key"),
            user_email=user.get("emailAddress"),
            changelog=changelog,
            raw=payload,
        )


class WebhookListener:
    """Flask-based webhook listener for Jira Cloud events.

    Usage:
        listener = WebhookListener(config)

        @listener.on("jira:issue_created")
        def handle_created(event: WebhookEvent):
            print(f"New issue: {event.issue_key}")

        listener.start()
    """

    # Common Jira webhook event types
    ISSUE_CREATED = "jira:issue_created"
    ISSUE_UPDATED = "jira:issue_updated"
    ISSUE_DELETED = "jira:issue_deleted"
    COMMENT_CREATED = "comment_created"
    COMMENT_UPDATED = "comment_updated"
    SPRINT_STARTED = "sprint_started"
    SPRINT_CLOSED = "sprint_closed"

    def __init__(self, config: JiraConfig | None = None):
        self.config = config or JiraConfig()
        self._handlers: dict[str, list[EventHandler]] = {}
        self._app = Flask(__name__)
        self._setup_routes()

    def on(self, event_type: str) -> Callable:
        """Decorator to register an event handler.

        Args:
            event_type: Jira webhook event type (e.g. "jira:issue_created")
        """
        def decorator(func: EventHandler) -> EventHandler:
            self._handlers.setdefault(event_type, []).append(func)
            return func
        return decorator

    def register_handler(self, event_type: str, handler: EventHandler) -> None:
        """Register an event handler programmatically."""
        self._handlers.setdefault(event_type, []).append(handler)

    def _setup_routes(self) -> None:
        @self._app.route("/webhook/jira", methods=["POST"])
        def handle_webhook():
            if self.config.webhook_secret:
                self._validate_signature(request)

            payload = request.get_json(silent=True)
            if not payload:
                abort(400, "Invalid JSON payload")

            event = WebhookEvent.from_payload(payload)
            logger.info(f"Received event: {event.event_type} (issue: {event.issue_key})")

            handlers = self._handlers.get(event.event_type, [])
            # Also call wildcard handlers registered with "*"
            handlers += self._handlers.get("*", [])

            for handler in handlers:
                try:
                    handler(event)
                except Exception:
                    logger.exception(f"Handler error for {event.event_type}")

            return jsonify({"status": "ok", "event": event.event_type}), 200

        @self._app.route("/health", methods=["GET"])
        def health():
            return jsonify({"status": "healthy"}), 200

    def _validate_signature(self, req: Request) -> None:
        """Validate webhook signature if a secret is configured."""
        signature = req.headers.get("X-Hub-Signature")
        if not signature:
            logger.warning("Webhook received without signature")
            abort(401, "Missing signature")

        body = req.get_data()
        expected = hmac.new(
            self.config.webhook_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(f"sha256={expected}", signature):
            logger.warning("Invalid webhook signature")
            abort(401, "Invalid signature")

    def start(self, host: str = "0.0.0.0", port: int | None = None, debug: bool = False) -> None:
        """Start the webhook listener server."""
        port = port or self.config.webhook_port
        logger.info(f"Starting webhook listener on {host}:{port}")
        self._app.run(host=host, port=port, debug=debug)

    @property
    def app(self) -> Flask:
        """Access the Flask app for testing or WSGI deployment."""
        return self._app
