"""Unit tests for the TransformService."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tng.domain.enums import (
    BarthesCode,
    FocalizationDistance,
    ReliabilityLevel,
    TransformAxis,
)
from tng.domain.models import Transform
from tng.repository.graph_repository import GraphRepository
from tng.services.transform_service import TransformRequest, TransformService


@pytest.fixture
def repo():
    r = MagicMock(spec=GraphRepository)

    def fake_apply(transform: Transform) -> Transform:
        transform.produced_id = f"produced-{transform.id}"
        return transform

    r.apply_transform.side_effect = fake_apply
    return r


@pytest.fixture
def svc(repo):
    return TransformService(repo)


class TestTransformServiceValidation:
    """Parameter validation tests."""

    def test_pov_valid_params(self, svc):
        req = TransformRequest(
            scene_id="s1",
            axis=TransformAxis.POV,
            parameters={"focalizer": "char-001", "distance": "internal", "reliability": "reliable"},
        )
        result = svc.apply(req)
        assert result.axis == "pov"
        assert result.status == "accepted"

    def test_pov_missing_focalizer_raises(self, svc):
        req = TransformRequest(
            scene_id="s1",
            axis=TransformAxis.POV,
            parameters={"distance": "zero"},
        )
        with pytest.raises(Exception):
            svc.apply(req)

    def test_mood_valid_params(self, svc):
        req = TransformRequest(
            scene_id="s1",
            axis=TransformAxis.MOOD,
            parameters={"label": "melancholic", "valence": -0.5, "arousal": 0.3},
        )
        result = svc.apply(req)
        assert result.axis == "mood"

    def test_mood_valence_out_of_range_raises(self, svc):
        req = TransformRequest(
            scene_id="s1",
            axis=TransformAxis.MOOD,
            parameters={"label": "angry", "valence": 2.0},
        )
        with pytest.raises(Exception):
            svc.apply(req)

    def test_genre_valid_params(self, svc):
        req = TransformRequest(
            scene_id="s1",
            axis=TransformAxis.GENRE,
            parameters={"name": "gothic", "conventions": ["dark atmosphere"]},
        )
        result = svc.apply(req)
        assert result.axis == "genre"

    def test_chronotope_valid_params(self, svc):
        req = TransformRequest(
            scene_id="s1",
            axis=TransformAxis.CHRONOTOPE,
            parameters={"time_mode": "cyclical", "space_mode": "liminal"},
        )
        result = svc.apply(req)
        assert result.axis == "chronotope"

    def test_chronotope_invalid_time_mode_raises(self, svc):
        req = TransformRequest(
            scene_id="s1",
            axis=TransformAxis.CHRONOTOPE,
            parameters={"time_mode": "weird", "space_mode": "bounded"},
        )
        with pytest.raises(Exception):
            svc.apply(req)

    def test_chronotope_invalid_space_mode_raises(self, svc):
        req = TransformRequest(
            scene_id="s1",
            axis=TransformAxis.CHRONOTOPE,
            parameters={"time_mode": "linear", "space_mode": "space_mode_x"},
        )
        with pytest.raises(Exception):
            svc.apply(req)

    def test_reliability_valid_params(self, svc):
        req = TransformRequest(
            scene_id="s1",
            axis=TransformAxis.RELIABILITY,
            parameters={"reliability": "unreliable"},
        )
        result = svc.apply(req)
        assert result.axis == "reliability"

    def test_code_overlay_valid_params(self, svc):
        req = TransformRequest(
            scene_id="s1",
            axis=TransformAxis.CODE_OVERLAY,
            parameters={"atom_id": "a1", "code": "semic", "label": "mood marker"},
        )
        result = svc.apply(req)
        assert result.axis == "code_overlay"

    def test_code_overlay_invalid_code_raises(self, svc):
        req = TransformRequest(
            scene_id="s1",
            axis=TransformAxis.CODE_OVERLAY,
            parameters={"atom_id": "a1", "code": "not_a_code"},
        )
        with pytest.raises(Exception):
            svc.apply(req)


class TestTransformServiceHistory:
    """History retrieval tests."""

    def test_get_history_calls_repo(self, svc, repo):
        repo.get_transform_history.return_value = [
            {"id": "t1", "axis": "pov", "operator": "user", "applied_at": "2026-01-01T00:00:00"}
        ]
        history = svc.get_history("scene-001")
        repo.get_transform_history.assert_called_once_with("scene-001")
        assert len(history) == 1
