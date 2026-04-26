"""API tests for pattern endpoints."""

from __future__ import annotations

import pytest


class TestCreatePattern:
    """Tests for ``POST /v1/patterns``."""

    def test_returns_201_on_creation(self, api_client):
        response = api_client.post(
            "/v1/patterns",
            json={"name": "Pursuit", "family": "pursuit", "description": "A chase."},
        )
        assert response.status_code == 201

    def test_returns_pattern_record(self, api_client):
        response = api_client.post(
            "/v1/patterns",
            json={"name": "Gift", "family": "ritual"},
        )
        data = response.json()
        assert "id" in data
        assert data["name"] == "Gift"
        assert data["family"] == "ritual"

    def test_uses_provided_id(self, api_client):
        response = api_client.post(
            "/v1/patterns",
            json={"id": "pattern.my-custom", "name": "Custom", "family": "ritual"},
        )
        assert response.json()["id"] == "pattern.my-custom"

    def test_missing_name_returns_422(self, api_client):
        response = api_client.post(
            "/v1/patterns",
            json={"family": "ritual"},
        )
        assert response.status_code == 422

    def test_missing_family_returns_422(self, api_client):
        response = api_client.post(
            "/v1/patterns",
            json={"name": "Test Pattern"},
        )
        assert response.status_code == 422


class TestListPatterns:
    """Tests for ``GET /v1/patterns``."""

    def test_returns_200_with_list(self, api_client):
        response = api_client.get("/v1/patterns")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_returns_pattern_records(self, api_client):
        response = api_client.get("/v1/patterns")
        for item in response.json():
            assert "id" in item
            assert "name" in item

    def test_family_filter_accepted(self, api_client, mock_repo):
        from tng.domain.models import Pattern
        mock_repo.list_patterns.return_value = [
            Pattern(id="p1", name="Gift Exchange", family="ritual")
        ]
        response = api_client.get("/v1/patterns?family=ritual")
        assert response.status_code == 200
        mock_repo.list_patterns.assert_called_with(family="ritual")


class TestListPatternInstances:
    """Tests for ``GET /v1/patterns/{id}/instances``."""

    def test_returns_404_for_unknown_pattern(self, api_client, mock_repo):
        mock_repo.get_pattern.return_value = None
        response = api_client.get(
            "/v1/patterns/unknown-pattern/instances?narrative_id=narr-001"
        )
        assert response.status_code == 404

    def test_returns_empty_list_when_no_instances(self, api_client, mock_repo):
        mock_repo.list_pattern_instances.return_value = []
        response = api_client.get(
            "/v1/patterns/pattern.gift_exchange/instances?narrative_id=narr-001"
        )
        assert response.status_code == 200
        assert response.json() == []
