"""API tests for ``POST /v1/render/{id}``."""

from __future__ import annotations

import json

import pytest


class TestRenderNarrative:
    """Tests for the render endpoint."""

    def test_prose_render_returns_200(self, api_client):
        response = api_client.post(
            "/v1/render/narr-001",
            json={"type": "prose"},
        )
        assert response.status_code == 200

    def test_render_response_has_required_fields(self, api_client):
        response = api_client.post(
            "/v1/render/narr-001",
            json={"type": "prose"},
        )
        data = response.json()
        for field in ["narrative_id", "render_type", "content", "content_type"]:
            assert field in data

    def test_render_type_reflected_in_response(self, api_client):
        response = api_client.post(
            "/v1/render/narr-001",
            json={"type": "markdown"},
        )
        assert response.json()["render_type"] == "markdown"

    def test_json_render_returns_valid_json_content(self, api_client):
        response = api_client.post(
            "/v1/render/narr-001",
            json={"type": "json"},
        )
        assert response.status_code == 200
        # The content field of the response should itself be parseable JSON
        content = response.json()["content"]
        doc = json.loads(content)
        assert "narrative" in doc

    def test_diff_render_returns_200(self, api_client):
        response = api_client.post(
            "/v1/render/narr-001",
            json={"type": "diff"},
        )
        assert response.status_code == 200

    def test_cypher_render_returns_200(self, api_client):
        response = api_client.post(
            "/v1/render/narr-001",
            json={"type": "cypher"},
        )
        assert response.status_code == 200

    def test_unknown_narrative_returns_404(self, api_client, mock_repo):
        mock_repo.get_graph_state.return_value = None
        response = api_client.post(
            "/v1/render/missing-id",
            json={"type": "prose"},
        )
        assert response.status_code == 404

    def test_invalid_render_type_returns_422(self, api_client):
        response = api_client.post(
            "/v1/render/narr-001",
            json={"type": "not_a_type"},
        )
        assert response.status_code == 422
