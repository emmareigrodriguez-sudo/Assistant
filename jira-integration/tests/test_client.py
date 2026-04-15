"""Tests for JiraClient using mocked HTTP responses."""

import json

import pytest
import responses

from src.client import JiraClient, JiraAPIError
from src.config import JiraConfig


@pytest.fixture
def config():
    return JiraConfig(
        jira_base_url="https://test.atlassian.net",
        jira_user_email="test@example.com",
        jira_api_token="fake-token",
    )


@pytest.fixture
def client(config):
    return JiraClient(config)


BASE = "https://test.atlassian.net/rest/api/3"
AGILE_BASE = "https://test.atlassian.net/rest/agile/1.0"


# ── Issue CRUD ─────────────────────────────────────────────────────


class TestCreateIssue:
    @responses.activate
    def test_creates_issue_with_required_fields(self, client):
        responses.add(
            responses.POST,
            f"{BASE}/issue",
            json={"id": "10001", "key": "PROJ-1", "self": f"{BASE}/issue/10001"},
            status=201,
        )

        result = client.create_issue(
            project_key="PROJ",
            summary="Test issue",
            issue_type="Story",
        )

        assert result["key"] == "PROJ-1"
        body = json.loads(responses.calls[0].request.body)
        assert body["fields"]["project"]["key"] == "PROJ"
        assert body["fields"]["summary"] == "Test issue"
        assert body["fields"]["issuetype"]["name"] == "Story"

    @responses.activate
    def test_creates_issue_with_all_fields(self, client):
        responses.add(
            responses.POST,
            f"{BASE}/issue",
            json={"id": "10002", "key": "PROJ-2", "self": f"{BASE}/issue/10002"},
            status=201,
        )

        result = client.create_issue(
            project_key="PROJ",
            summary="Full issue",
            issue_type="Bug",
            description="A bug description",
            priority="High",
            assignee_account_id="abc123",
            labels=["urgent", "backend"],
        )

        assert result["key"] == "PROJ-2"
        body = json.loads(responses.calls[0].request.body)
        assert body["fields"]["priority"]["name"] == "High"
        assert body["fields"]["assignee"]["accountId"] == "abc123"
        assert body["fields"]["labels"] == ["urgent", "backend"]
        # Description should be ADF
        assert body["fields"]["description"]["type"] == "doc"


class TestGetIssue:
    @responses.activate
    def test_returns_issue_data(self, client):
        responses.add(
            responses.GET,
            f"{BASE}/issue/PROJ-1",
            json={
                "key": "PROJ-1",
                "fields": {
                    "summary": "Test",
                    "status": {"name": "To Do"},
                },
            },
        )

        issue = client.get_issue("PROJ-1")
        assert issue["key"] == "PROJ-1"
        assert issue["fields"]["status"]["name"] == "To Do"

    @responses.activate
    def test_with_specific_fields(self, client):
        responses.add(responses.GET, f"{BASE}/issue/PROJ-1", json={"key": "PROJ-1", "fields": {}})

        client.get_issue("PROJ-1", fields=["summary", "status"])
        assert "fields=summary%2Cstatus" in responses.calls[0].request.url


class TestUpdateIssue:
    @responses.activate
    def test_updates_summary(self, client):
        responses.add(responses.PUT, f"{BASE}/issue/PROJ-1", status=204)

        client.update_issue("PROJ-1", summary="Updated title")
        body = json.loads(responses.calls[0].request.body)
        assert body["fields"]["summary"] == "Updated title"


class TestDeleteIssue:
    @responses.activate
    def test_deletes_issue(self, client):
        responses.add(responses.DELETE, f"{BASE}/issue/PROJ-1", status=204)
        client.delete_issue("PROJ-1")
        assert responses.calls[0].request.method == "DELETE"


class TestTransitionIssue:
    @responses.activate
    def test_transitions_by_name(self, client):
        responses.add(
            responses.GET,
            f"{BASE}/issue/PROJ-1/transitions",
            json={
                "transitions": [
                    {"id": "21", "name": "In Progress"},
                    {"id": "31", "name": "Done"},
                ]
            },
        )
        responses.add(responses.POST, f"{BASE}/issue/PROJ-1/transitions", status=204)

        client.transition_issue("PROJ-1", "Done")
        body = json.loads(responses.calls[1].request.body)
        assert body["transition"]["id"] == "31"

    @responses.activate
    def test_raises_on_invalid_transition(self, client):
        responses.add(
            responses.GET,
            f"{BASE}/issue/PROJ-1/transitions",
            json={"transitions": [{"id": "21", "name": "In Progress"}]},
        )

        with pytest.raises(ValueError, match="not found"):
            client.transition_issue("PROJ-1", "Nonexistent")


# ── Search ─────────────────────────────────────────────────────────


class TestSearch:
    @responses.activate
    def test_search_returns_issues(self, client):
        responses.add(
            responses.POST,
            f"{BASE}/search",
            json={
                "issues": [
                    {"key": "PROJ-1", "fields": {"summary": "Issue 1"}},
                    {"key": "PROJ-2", "fields": {"summary": "Issue 2"}},
                ],
                "total": 2,
            },
        )

        results = client.search_issues("project = PROJ")
        assert len(results) == 2
        assert results[0]["key"] == "PROJ-1"


# ── Error handling ─────────────────────────────────────────────────


class TestErrorHandling:
    @responses.activate
    def test_raises_on_404(self, client):
        responses.add(
            responses.GET,
            f"{BASE}/issue/NOPE-999",
            json={"errorMessages": ["Issue does not exist"]},
            status=404,
        )

        with pytest.raises(JiraAPIError) as exc_info:
            client.get_issue("NOPE-999")
        assert exc_info.value.status_code == 404

    @responses.activate
    def test_raises_on_401(self, client):
        responses.add(
            responses.GET,
            f"{BASE}/myself",
            json={"errorMessages": ["Unauthorized"]},
            status=401,
        )

        with pytest.raises(JiraAPIError) as exc_info:
            client.get_myself()
        assert exc_info.value.status_code == 401


# ── ADF conversion ────────────────────────────────────────────────


class TestADF:
    def test_plain_text_to_adf(self, client):
        adf = client._to_adf("Hello world")
        assert adf["type"] == "doc"
        assert adf["version"] == 1
        assert len(adf["content"]) == 1
        assert adf["content"][0]["content"][0]["text"] == "Hello world"

    def test_multiline_to_adf(self, client):
        adf = client._to_adf("Paragraph 1\n\nParagraph 2")
        assert len(adf["content"]) == 2

    def test_adf_passthrough(self, client):
        existing = {"type": "doc", "version": 1, "content": []}
        assert client._to_adf(existing) is existing


# ── Agile API ──────────────────────────────────────────────────────


class TestAgileAPI:
    @responses.activate
    def test_get_boards(self, client):
        responses.add(
            responses.GET,
            f"{AGILE_BASE}/board",
            json={
                "values": [{"id": 1, "name": "HEALTH board"}],
                "total": 1,
            },
        )

        boards = client.get_boards(project_key="HEALTH")
        assert len(boards) == 1
        assert boards[0]["name"] == "HEALTH board"

    @responses.activate
    def test_get_sprints(self, client):
        responses.add(
            responses.GET,
            f"{AGILE_BASE}/board/1/sprint",
            json={
                "values": [
                    {"id": 10, "name": "Sprint 14", "state": "active"},
                ],
                "total": 1,
            },
        )

        sprints = client.get_sprints(1, state="active")
        assert len(sprints) == 1
        assert sprints[0]["state"] == "active"
