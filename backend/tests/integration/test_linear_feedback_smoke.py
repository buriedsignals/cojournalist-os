"""
Live Linear smoke test for the in-app feedback integration.

This test mutates the Linear workspace, so it is opt-in only:

    RUN_LINEAR_SMOKE=1 LINEAR_API_KEY=lin_api_... python -m pytest \
        tests/integration/test_linear_feedback_smoke.py -v

It creates a clearly marked smoke issue, verifies Linear returns a URL, and
archives the issue in cleanup.
"""
import os
from uuid import uuid4

import httpx
import pytest

from app.routers.feedback import _BASE_LABEL_NAMES, _LINEAR_TEAM_ID, _TYPE_LABEL_NAMES


LINEAR_GRAPHQL_URL = "https://api.linear.app/graphql"


def _require_smoke_env() -> str:
    if os.getenv("RUN_LINEAR_SMOKE") != "1":
        pytest.skip("Set RUN_LINEAR_SMOKE=1 to run live Linear smoke test")
    api_key = os.getenv("LINEAR_API_KEY")
    if not api_key:
        pytest.skip("LINEAR_API_KEY is required for live Linear smoke test")
    return api_key


def _linear_graphql(api_key: str, query: str, variables: dict | None = None) -> dict:
    response = httpx.post(
        LINEAR_GRAPHQL_URL,
        headers={
            "Authorization": api_key,
            "Content-Type": "application/json",
        },
        json={"query": query, "variables": variables or {}},
        timeout=10.0,
    )
    response.raise_for_status()
    body = response.json()
    assert "errors" not in body, body["errors"]
    return body["data"]


def test_linear_feedback_smoke_creates_and_archives_issue():
    api_key = _require_smoke_env()
    issue_id = None

    try:
        metadata = _linear_graphql(
            api_key,
            """
            query FeedbackSmokeMetadata {
              teams(first: 100) {
                nodes { id key name }
              }
              issueLabels(first: 100) {
                nodes { id name }
              }
            }
            """,
        )
        teams_by_id = {
            team["id"]: team
            for team in metadata["teams"]["nodes"]
        }
        assert _LINEAR_TEAM_ID in teams_by_id

        labels_by_name = {
            label["name"].casefold(): label["id"]
            for label in metadata["issueLabels"]["nodes"]
        }
        wanted_label_names = [*_BASE_LABEL_NAMES, *_TYPE_LABEL_NAMES["bug"]]
        missing_labels = [
            name
            for name in wanted_label_names
            if name.casefold() not in labels_by_name
        ]
        assert not missing_labels, f"Missing Linear labels: {missing_labels}"
        label_ids = [
            labels_by_name[name.casefold()]
            for name in wanted_label_names
        ]

        title = f"[smoke] coJournalist feedback integration {uuid4()}"
        created = _linear_graphql(
            api_key,
            """
            mutation FeedbackSmokeIssueCreate($input: IssueCreateInput!) {
              issueCreate(input: $input) {
                success
                issue { id identifier url title }
              }
            }
            """,
            {
                "input": {
                    "teamId": _LINEAR_TEAM_ID,
                    "title": title,
                    "description": (
                        "Automated smoke test for coJournalist feedback. "
                        "This issue should be archived automatically."
                    ),
                    "labelIds": label_ids,
                }
            },
        )
        issue = created["issueCreate"]["issue"]
        issue_id = issue["id"]

        assert created["issueCreate"]["success"] is True
        assert issue["title"] == title
        assert issue["url"].startswith("https://linear.app/")
        assert issue["identifier"]
    finally:
        if issue_id:
            archived = _linear_graphql(
                api_key,
                """
                mutation FeedbackSmokeIssueArchive($id: String!) {
                  issueArchive(id: $id) {
                    success
                  }
                }
                """,
                {"id": issue_id},
            )
            assert archived["issueArchive"]["success"] is True
