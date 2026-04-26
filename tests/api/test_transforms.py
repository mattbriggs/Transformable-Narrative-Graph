"""API tests for transform endpoints."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from tng.domain.models import Transform
from tng.domain.enums import TransformAxis


class TestApplyTransform:
    """Tests for ``POST /v1/transforms/apply``."""

    def test_pov_transform_returns_200(self, api_client, mock_repo):
        def fake_apply(t: Transform) -> Transform:
            t.produced_id = "pov-test-001"
            return t

        mock_repo.apply_transform.side_effect = fake_apply

        response = api_client.post(
            "/v1/transforms/apply",
            json={
                "scene_id": "scene-001",
                "axis": "pov",
                "parameters": {
                    "focalizer": "char-001",
                    "distance": "internal",
                    "reliability": "reliable",
                },
            },
        )
        assert response.status_code == 200

    def test_pov_transform_response_has_required_fields(self, api_client, mock_repo):
        def fake_apply(t: Transform) -> Transform:
            t.produced_id = "pov-001"
            return t

        mock_repo.apply_transform.side_effect = fake_apply
        response = api_client.post(
            "/v1/transforms/apply",
            json={
                "scene_id": "s1",
                "axis": "pov",
                "parameters": {"focalizer": "c1"},
            },
        )
        data = response.json()
        for field in ["transform_id", "scene_id", "axis", "produced_id", "status"]:
            assert field in data

    def test_invalid_axis_returns_422(self, api_client):
        response = api_client.post(
            "/v1/transforms/apply",
            json={
                "scene_id": "s1",
                "axis": "not_an_axis",
                "parameters": {},
            },
        )
        assert response.status_code == 422

    def test_missing_focalizer_in_pov_returns_400(self, api_client, mock_repo):
        def raise_value_error(t):
            raise ValueError("focalizer is required")

        mock_repo.apply_transform.side_effect = raise_value_error
        response = api_client.post(
            "/v1/transforms/apply",
            json={
                "scene_id": "s1",
                "axis": "pov",
                "parameters": {"distance": "zero"},
            },
        )
        assert response.status_code == 400

    def test_mood_transform(self, api_client, mock_repo):
        def fake_apply(t: Transform) -> Transform:
            t.produced_id = "mood-001"
            return t

        mock_repo.apply_transform.side_effect = fake_apply
        response = api_client.post(
            "/v1/transforms/apply",
            json={
                "scene_id": "s1",
                "axis": "mood",
                "parameters": {"label": "melancholic", "valence": -0.5, "arousal": 0.3},
            },
        )
        assert response.status_code == 200

    def test_genre_transform(self, api_client, mock_repo):
        def fake_apply(t: Transform) -> Transform:
            t.produced_id = "genre-001"
            return t

        mock_repo.apply_transform.side_effect = fake_apply
        response = api_client.post(
            "/v1/transforms/apply",
            json={
                "scene_id": "s1",
                "axis": "genre",
                "parameters": {"name": "gothic"},
            },
        )
        assert response.status_code == 200


class TestGetTransform:
    """Tests for ``GET /v1/transforms/{id}``."""

    def test_returns_200_for_existing_transform(self, api_client):
        response = api_client.get("/v1/transforms/t-001")
        assert response.status_code == 200

    def test_returns_404_for_missing_transform(self, api_client, mock_repo):
        mock_repo.get_transform.return_value = None
        response = api_client.get("/v1/transforms/missing")
        assert response.status_code == 404

    def test_returns_transform_fields(self, api_client):
        response = api_client.get("/v1/transforms/t-001")
        data = response.json()
        assert "id" in data
        assert "scene_id" in data
