"""API tests for ``GET /v1/narratives/{id}`` and ``DELETE /v1/narratives/{id}``."""

from __future__ import annotations

import pytest


class TestGetNarrative:
    """Tests for the narrative retrieval endpoint."""

    def test_returns_200_for_existing_narrative(self, api_client):
        response = api_client.get("/v1/narratives/narr-001")
        assert response.status_code == 200

    def test_returns_narrative_fields(self, api_client):
        response = api_client.get("/v1/narratives/narr-001")
        data = response.json()
        assert data["id"] == "narr-001"
        assert data["title"] == "Test Narrative"
        assert "status" in data
        assert "scene_count" in data

    def test_returns_404_for_unknown_narrative(self, api_client, mock_repo):
        mock_repo.get_narrative.return_value = None
        response = api_client.get("/v1/narratives/unknown-id")
        assert response.status_code == 404

    def test_404_error_message_contains_id(self, api_client, mock_repo):
        mock_repo.get_narrative.return_value = None
        response = api_client.get("/v1/narratives/missing-id")
        assert "missing-id" in response.json()["detail"]


class TestDeleteNarrative:
    """Tests for the narrative archive endpoint."""

    def test_returns_204_on_archive(self, api_client):
        response = api_client.delete("/v1/narratives/narr-001")
        assert response.status_code == 204

    def test_returns_404_when_not_found(self, api_client, mock_repo):
        mock_repo.archive_narrative.return_value = False
        response = api_client.delete("/v1/narratives/unknown")
        assert response.status_code == 404
