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


class TestApplyBulkTransform:
    """Tests for ``POST /v1/transforms/apply-bulk``."""

    def test_bulk_apply_returns_200(self, api_client, mock_repo):
        def fake_apply(t):
            t.produced_id = "mood-bulk-001"
            return t

        mock_repo.apply_transform.side_effect = fake_apply
        response = api_client.post(
            "/v1/transforms/apply-bulk",
            json={
                "narrative_id": "narr-001",
                "axis": "mood",
                "parameters": {"label": "dread", "valence": -0.8, "arousal": 0.7},
            },
        )
        assert response.status_code == 200

    def test_bulk_apply_applied_count_matches_scenes(self, api_client, mock_repo):
        mock_repo.get_scene_ids.return_value = ["s1", "s2", "s3"]

        def fake_apply(t):
            t.produced_id = "m-001"
            return t

        mock_repo.apply_transform.side_effect = fake_apply
        response = api_client.post(
            "/v1/transforms/apply-bulk",
            json={
                "narrative_id": "narr-001",
                "axis": "mood",
                "parameters": {"label": "hope", "valence": 0.5, "arousal": 0.4},
            },
        )
        data = response.json()
        assert data["applied_count"] == 3
        assert len(data["results"]) == 3

    def test_bulk_apply_no_scenes_returns_400(self, api_client, mock_repo):
        mock_repo.get_scene_ids.return_value = []
        response = api_client.post(
            "/v1/transforms/apply-bulk",
            json={
                "narrative_id": "empty-narr",
                "axis": "mood",
                "parameters": {"label": "calm"},
            },
        )
        assert response.status_code == 400

    def test_bulk_apply_invalid_params_returns_400(self, api_client, mock_repo):
        response = api_client.post(
            "/v1/transforms/apply-bulk",
            json={
                "narrative_id": "narr-001",
                "axis": "mood",
                "parameters": {"valence": 99.0},
            },
        )
        assert response.status_code == 400

    def test_bulk_apply_response_contains_narrative_id(self, api_client, mock_repo):
        def fake_apply(t):
            t.produced_id = "p1"
            return t

        mock_repo.apply_transform.side_effect = fake_apply
        response = api_client.post(
            "/v1/transforms/apply-bulk",
            json={
                "narrative_id": "narr-001",
                "axis": "genre",
                "parameters": {"name": "gothic"},
            },
        )
        assert response.json()["narrative_id"] == "narr-001"


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
