import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers import feedback as feedback_module


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeAsyncClient:
    def __init__(self, responses: list[dict]):
        self.responses = responses
        self.posts: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url, **kwargs):  # noqa: ARG002
        self.posts.append(kwargs)
        return _FakeResponse(self.responses.pop(0))


def test_submit_feedback_resolves_current_label_ids_before_issue_create(monkeypatch):
    fake_client = _FakeAsyncClient(
        [
            {
                "data": {
                    "issueLabels": {
                        "nodes": [
                            {"id": "label-cojournalist", "name": "cojournalist"},
                            {"id": "label-bug", "name": "Bug"},
                        ]
                    }
                }
            },
            {
                "data": {
                    "issueCreate": {
                        "success": True,
                        "issue": {"url": "https://linear.app/team/issue/COJ-123/test"},
                    }
                }
            },
        ]
    )
    monkeypatch.setattr(feedback_module.limiter, "enabled", False)
    monkeypatch.setattr(feedback_module.httpx, "AsyncClient", lambda: fake_client)
    monkeypatch.setattr(
        feedback_module,
        "get_settings",
        lambda: SimpleNamespace(linear_api_key="lin_api_test"),
    )

    response = asyncio.run(
        feedback_module.submit_feedback(
            request=SimpleNamespace(),
            feedback=feedback_module.FeedbackRequest(
                title="Bug report",
                type="bug",
                description="Something broke",
                device="Mac",
                browser="Chrome",
            ),
            current_user={"email": "reporter@example.com"},
        )
    )

    assert response.url == "https://linear.app/team/issue/COJ-123/test"
    assert len(fake_client.posts) == 2
    create_input = fake_client.posts[1]["json"]["variables"]["input"]
    assert create_input["labelIds"] == ["label-cojournalist", "label-bug"]


def test_submit_feedback_creates_issue_without_labels_when_label_lookup_misses(monkeypatch):
    fake_client = _FakeAsyncClient(
        [
            {"data": {"issueLabels": {"nodes": []}}},
            {
                "data": {
                    "issueCreate": {
                        "success": True,
                        "issue": {"url": "https://linear.app/team/issue/COJ-124/test"},
                    }
                }
            },
        ]
    )
    monkeypatch.setattr(feedback_module.limiter, "enabled", False)
    monkeypatch.setattr(feedback_module.httpx, "AsyncClient", lambda: fake_client)
    monkeypatch.setattr(
        feedback_module,
        "get_settings",
        lambda: SimpleNamespace(linear_api_key="lin_api_test"),
    )

    response = asyncio.run(
        feedback_module.submit_feedback(
            request=SimpleNamespace(),
            feedback=feedback_module.FeedbackRequest(
                title="Bug report",
                type="bug",
                description="Something broke",
            ),
            current_user={"email": "reporter@example.com"},
        )
    )

    assert response.url == "https://linear.app/team/issue/COJ-124/test"
    create_input = fake_client.posts[1]["json"]["variables"]["input"]
    assert "labelIds" not in create_input


def test_submit_feedback_does_not_retry_linear_issue_create_errors(monkeypatch):
    fake_client = _FakeAsyncClient(
        [
            {
                "data": {
                    "issueLabels": {
                        "nodes": [
                            {"id": "label-cojournalist", "name": "cojournalist"},
                            {"id": "label-bug", "name": "bug"},
                        ]
                    }
                }
            },
            {"errors": [{"message": "Authentication required"}]},
        ]
    )
    monkeypatch.setattr(feedback_module.limiter, "enabled", False)
    monkeypatch.setattr(feedback_module.httpx, "AsyncClient", lambda: fake_client)
    monkeypatch.setattr(
        feedback_module,
        "get_settings",
        lambda: SimpleNamespace(linear_api_key="lin_api_test"),
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            feedback_module.submit_feedback(
                request=SimpleNamespace(),
                feedback=feedback_module.FeedbackRequest(
                    title="Bug report",
                    type="bug",
                    description="Something broke",
                ),
                current_user={"email": "reporter@example.com"},
            )
        )

    assert exc_info.value.status_code == 502
    assert len(fake_client.posts) == 2
