"""API tests for the health endpoints."""

from __future__ import annotations

import pytest


class TestLiveness:
    """Tests for ``GET /v1/health/live``."""

    def test_returns_200(self, api_client):
        response = api_client.get("/v1/health/live")
        assert response.status_code == 200

    def test_returns_ok_status(self, api_client):
        response = api_client.get("/v1/health/live")
        assert response.json()["status"] == "ok"


class TestReadiness:
    """Tests for ``GET /v1/health/ready``."""

    def test_returns_200_when_neo4j_reachable(self, api_client):
        response = api_client.get("/v1/health/ready")
        assert response.status_code == 200

    def test_returns_neo4j_reachable_field(self, api_client):
        response = api_client.get("/v1/health/ready")
        assert response.json()["neo4j"] == "reachable"

    def test_returns_503_when_neo4j_unreachable(self, api_client, mock_repo):
        mock_repo.ping.side_effect = Exception("Connection refused")
        response = api_client.get("/v1/health/ready")
        assert response.status_code == 503
