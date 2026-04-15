"""Jira Cloud REST API client with authentication, retries, and error handling."""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import JiraConfig, setup_logging


class JiraAPIError(Exception):
    """Raised when the Jira API returns an error response."""

    def __init__(self, status_code: int, message: str, errors: list[str] | None = None):
        self.status_code = status_code
        self.errors = errors or []
        super().__init__(f"Jira API {status_code}: {message}")


class JiraClient:
    """Client for Jira Cloud REST API v3 and Agile API.

    Usage:
        config = JiraConfig()  # loads from env
        client = JiraClient(config)
        issues = client.search_issues('project = PROJ')
    """

    API_V3 = "/rest/api/3"
    AGILE_API = "/rest/agile/1.0"

    def __init__(self, config: JiraConfig | None = None):
        self.config = config or JiraConfig()
        self.logger = setup_logging(self.config)
        self._session = self._build_session()

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        session.auth = (self.config.jira_user_email, self.config.jira_api_token)
        session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        return session

    # ── Core HTTP methods ──────────────────────────────────────────────

    def _url(self, path: str, agile: bool = False) -> str:
        base = self.AGILE_API if agile else self.API_V3
        return f"{self.config.jira_base_url}{base}{path}"

    def _request(
        self,
        method: str,
        path: str,
        agile: bool = False,
        params: dict | None = None,
        json_data: dict | None = None,
    ) -> dict | list | None:
        url = self._url(path, agile=agile)
        self.logger.debug(f"{method} {path}")

        response = self._session.request(
            method=method,
            url=url,
            params=params,
            json=json_data,
            timeout=self.config.request_timeout,
        )

        if response.status_code == 204:
            return None

        if not response.ok:
            self._handle_error(response)

        return response.json() if response.content else None

    def _handle_error(self, response: requests.Response) -> None:
        try:
            body = response.json()
            messages = body.get("errorMessages", [])
            errors = body.get("errors", {})
            detail = "; ".join(messages) if messages else str(errors)
        except Exception:
            detail = response.text[:500]

        self.logger.error(f"API error {response.status_code}: {detail}")
        raise JiraAPIError(response.status_code, detail)

    def get(self, path: str, params: dict | None = None, agile: bool = False) -> Any:
        return self._request("GET", path, agile=agile, params=params)

    def post(self, path: str, data: dict | None = None, agile: bool = False) -> Any:
        return self._request("POST", path, agile=agile, json_data=data)

    def put(self, path: str, data: dict | None = None, agile: bool = False) -> Any:
        return self._request("PUT", path, agile=agile, json_data=data)

    def delete(self, path: str, agile: bool = False) -> Any:
        return self._request("DELETE", path, agile=agile)

    # ── Pagination helper ──────────────────────────────────────────────

    def paginate(
        self,
        path: str,
        params: dict | None = None,
        agile: bool = False,
        results_key: str = "values",
        max_results: int | None = None,
    ) -> list[dict]:
        """Auto-paginate through Jira API results."""
        params = dict(params or {})
        params.setdefault("startAt", 0)
        params.setdefault("maxResults", 50)

        all_results: list[dict] = []

        while True:
            data = self.get(path, params=params, agile=agile)

            # REST API v3 uses 'issues', Agile API uses 'values'
            items = data.get(results_key, data.get("issues", []))
            all_results.extend(items)

            total = data.get("total", len(all_results))
            if max_results and len(all_results) >= max_results:
                return all_results[:max_results]

            params["startAt"] += len(items)
            if params["startAt"] >= total or not items:
                break

        return all_results

    # ── Issues ─────────────────────────────────────────────────────────

    def create_issue(
        self,
        project_key: str,
        summary: str,
        issue_type: str = "Task",
        description: str | None = None,
        priority: str | None = None,
        assignee_account_id: str | None = None,
        labels: list[str] | None = None,
        custom_fields: dict | None = None,
    ) -> dict:
        """Create a new issue.

        Args:
            project_key: Project key (e.g. "PROJ")
            summary: Issue title
            issue_type: Task, Story, Bug, Epic, Sub-task
            description: ADF-formatted description or plain text (auto-converted)
            priority: Priority name (e.g. "High", "Medium")
            assignee_account_id: Atlassian account ID of the assignee
            labels: List of label strings
            custom_fields: Dict of custom field IDs to values

        Returns:
            Created issue data with id, key, and self URL.
        """
        fields: dict[str, Any] = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }

        if description:
            fields["description"] = self._to_adf(description)

        if priority:
            fields["priority"] = {"name": priority}

        if assignee_account_id:
            fields["assignee"] = {"accountId": assignee_account_id}

        if labels:
            fields["labels"] = labels

        if custom_fields:
            fields.update(custom_fields)

        result = self.post("/issue", data={"fields": fields})
        self.logger.info(f"Created issue {result['key']}")
        return result

    def get_issue(self, issue_key: str, fields: list[str] | None = None) -> dict:
        """Get a single issue by key (e.g. 'PROJ-123')."""
        params = {}
        if fields:
            params["fields"] = ",".join(fields)
        return self.get(f"/issue/{issue_key}", params=params)

    def update_issue(self, issue_key: str, fields: dict | None = None, **kwargs) -> None:
        """Update issue fields.

        Args:
            issue_key: Issue key (e.g. "PROJ-123")
            fields: Dict of field names/IDs to new values
            **kwargs: Shorthand — summary, description, priority, labels, assignee_account_id
        """
        update_fields: dict[str, Any] = dict(fields or {})

        if "summary" in kwargs:
            update_fields["summary"] = kwargs["summary"]
        if "description" in kwargs:
            update_fields["description"] = self._to_adf(kwargs["description"])
        if "priority" in kwargs:
            update_fields["priority"] = {"name": kwargs["priority"]}
        if "labels" in kwargs:
            update_fields["labels"] = kwargs["labels"]
        if "assignee_account_id" in kwargs:
            update_fields["assignee"] = {"accountId": kwargs["assignee_account_id"]}

        self.put(f"/issue/{issue_key}", data={"fields": update_fields})
        self.logger.info(f"Updated issue {issue_key}")

    def delete_issue(self, issue_key: str, delete_subtasks: bool = True) -> None:
        """Delete an issue. Subtasks are deleted by default."""
        params = {"deleteSubtasks": str(delete_subtasks).lower()}
        self._request("DELETE", f"/issue/{issue_key}", params=params)
        self.logger.info(f"Deleted issue {issue_key}")

    def transition_issue(self, issue_key: str, transition_name: str) -> None:
        """Move an issue to a new status by transition name (e.g. 'Done', 'In Progress')."""
        transitions = self.get(f"/issue/{issue_key}/transitions")
        match = next(
            (t for t in transitions["transitions"] if t["name"].lower() == transition_name.lower()),
            None,
        )
        if not match:
            available = [t["name"] for t in transitions["transitions"]]
            raise ValueError(
                f"Transition '{transition_name}' not found. Available: {available}"
            )

        self.post(f"/issue/{issue_key}/transitions", data={"transition": {"id": match["id"]}})
        self.logger.info(f"Transitioned {issue_key} → {transition_name}")

    def add_comment(self, issue_key: str, body: str) -> dict:
        """Add a comment to an issue."""
        return self.post(
            f"/issue/{issue_key}/comment",
            data={"body": self._to_adf(body)},
        )

    def get_comments(self, issue_key: str) -> list[dict]:
        """Get all comments on an issue."""
        data = self.get(f"/issue/{issue_key}/comment")
        return data.get("comments", [])

    def assign_issue(self, issue_key: str, account_id: str | None) -> None:
        """Assign an issue. Pass None to unassign."""
        self.put(f"/issue/{issue_key}/assignee", data={"accountId": account_id})

    def add_labels(self, issue_key: str, labels: list[str]) -> None:
        """Add labels to an issue without removing existing ones."""
        update = {"update": {"labels": [{"add": label} for label in labels]}}
        self.put(f"/issue/{issue_key}", data=update)

    def link_issues(
        self, inward_key: str, outward_key: str, link_type: str = "Relates"
    ) -> None:
        """Create a link between two issues."""
        self.post("/issueLink", data={
            "type": {"name": link_type},
            "inwardIssue": {"key": inward_key},
            "outwardIssue": {"key": outward_key},
        })

    # ── Search (JQL) ───────────────────────────────────────────────────

    def search_issues(
        self,
        jql: str,
        fields: list[str] | None = None,
        max_results: int = 50,
    ) -> list[dict]:
        """Search issues using JQL.

        Args:
            jql: JQL query string (e.g. "project = PROJ AND status = 'To Do'")
            fields: List of fields to return (default: all navigable)
            max_results: Maximum number of results

        Returns:
            List of issue dicts.
        """
        data = {
            "jql": jql,
            "maxResults": min(max_results, 100),
            "fields": fields or ["summary", "status", "assignee", "priority", "created", "updated"],
        }

        all_issues: list[dict] = []
        start_at = 0

        while len(all_issues) < max_results:
            data["startAt"] = start_at
            result = self.post("/search", data=data)
            issues = result.get("issues", [])
            all_issues.extend(issues)

            if start_at + len(issues) >= result.get("total", 0) or not issues:
                break
            start_at += len(issues)

        return all_issues[:max_results]

    # ── Projects ───────────────────────────────────────────────────────

    def get_projects(self) -> list[dict]:
        """List all accessible projects."""
        return self.paginate("/project/search", results_key="values")

    def get_project(self, project_key: str) -> dict:
        """Get project details."""
        return self.get(f"/project/{project_key}")

    # ── Users ──────────────────────────────────────────────────────────

    def search_users(self, query: str, max_results: int = 10) -> list[dict]:
        """Search for users by name or email."""
        return self.get("/user/search", params={"query": query, "maxResults": max_results})

    def get_myself(self) -> dict:
        """Get the authenticated user's profile."""
        return self.get("/myself")

    # ── Boards & Sprints (Agile API) ───────────────────────────────────

    def get_boards(self, project_key: str | None = None) -> list[dict]:
        """List boards, optionally filtered by project."""
        params = {}
        if project_key:
            params["projectKeyOrId"] = project_key
        return self.paginate("/board", params=params, agile=True)

    def get_sprints(
        self, board_id: int, state: str | None = None
    ) -> list[dict]:
        """List sprints for a board.

        Args:
            board_id: Board ID
            state: Filter by state — 'active', 'future', 'closed'
        """
        params = {}
        if state:
            params["state"] = state
        return self.paginate(f"/board/{board_id}/sprint", params=params, agile=True)

    def get_sprint_issues(self, sprint_id: int) -> list[dict]:
        """Get all issues in a sprint."""
        return self.paginate(
            f"/sprint/{sprint_id}/issue",
            agile=True,
            results_key="issues",
        )

    def get_backlog(self, board_id: int) -> list[dict]:
        """Get backlog issues for a board."""
        return self.paginate(
            f"/board/{board_id}/backlog",
            agile=True,
            results_key="issues",
        )

    # ── Epics ──────────────────────────────────────────────────────────

    def get_epics(self, board_id: int) -> list[dict]:
        """List epics for a board."""
        return self.paginate(f"/board/{board_id}/epic", agile=True)

    def get_epic_issues(self, epic_id: int) -> list[dict]:
        """Get issues belonging to an epic."""
        return self.paginate(
            f"/epic/{epic_id}/issue",
            agile=True,
            results_key="issues",
        )

    # ── Statuses & Priorities ──────────────────────────────────────────

    def get_statuses(self) -> list[dict]:
        """List all available statuses."""
        return self.get("/status")

    def get_priorities(self) -> list[dict]:
        """List all available priorities."""
        return self.get("/priority")

    def get_issue_types(self, project_key: str) -> list[dict]:
        """List issue types available in a project."""
        project = self.get_project(project_key)
        return project.get("issueTypes", [])

    # ── Watchers ───────────────────────────────────────────────────────

    def add_watcher(self, issue_key: str, account_id: str) -> None:
        """Add a watcher to an issue."""
        self.post(f"/issue/{issue_key}/watchers", data=account_id)

    # ── Attachments ────────────────────────────────────────────────────

    def get_attachments(self, issue_key: str) -> list[dict]:
        """Get attachments for an issue."""
        issue = self.get_issue(issue_key, fields=["attachment"])
        return issue.get("fields", {}).get("attachment", [])

    # ── Bulk operations ────────────────────────────────────────────────

    def bulk_create_issues(self, issues: list[dict]) -> dict:
        """Create multiple issues at once.

        Args:
            issues: List of issue field dicts (same format as create_issue fields)

        Returns:
            Dict with 'issues' (created) and 'errors' lists.
        """
        payload = {"issueUpdates": [{"fields": fields} for fields in issues]}
        return self.post("/issue/bulk", data=payload)

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _to_adf(text: str) -> dict:
        """Convert plain text to Atlassian Document Format (ADF).

        If the input is already an ADF dict, return it as-is.
        """
        if isinstance(text, dict) and text.get("type") == "doc":
            return text

        paragraphs = text.split("\n\n") if "\n\n" in text else [text]
        content = []
        for para in paragraphs:
            content.append({
                "type": "paragraph",
                "content": [{"type": "text", "text": para}],
            })

        return {
            "version": 1,
            "type": "doc",
            "content": content,
        }
