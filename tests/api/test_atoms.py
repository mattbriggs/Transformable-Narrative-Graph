"""API tests for atom revision endpoints."""

from __future__ import annotations

from datetime import datetime


class TestReviseAtom:
    """Tests for ``PATCH /v1/atoms/{atom_id}``."""

    def test_revise_returns_200(self, api_client):
        response = api_client.patch(
            "/v1/atoms/atom-001",
            json={"text": "She hesitated at the threshold."},
        )
        assert response.status_code == 200

    def test_revise_response_contains_required_fields(self, api_client):
        response = api_client.patch(
            "/v1/atoms/atom-001",
            json={"text": "Revised sentence."},
        )
        data = response.json()
        for field in ["atom_id", "revision_id", "text"]:
            assert field in data

    def test_revise_response_text_matches_request(self, api_client):
        new_text = "She did not answer, but her silence said everything."
        response = api_client.patch(
            "/v1/atoms/atom-001",
            json={"text": new_text},
        )
        assert response.json()["text"] == new_text

    def test_revise_response_atom_id_matches(self, api_client):
        response = api_client.patch(
            "/v1/atoms/atom-001",
            json={"text": "New text."},
        )
        assert response.json()["atom_id"] == "atom-001"

    def test_revise_not_found_returns_404(self, api_client, mock_repo):
        mock_repo.revise_atom.return_value = False
        response = api_client.patch(
            "/v1/atoms/missing-atom",
            json={"text": "Some text."},
        )
        assert response.status_code == 404

    def test_revise_with_reason(self, api_client, mock_repo):
        response = api_client.patch(
            "/v1/atoms/atom-001",
            json={"text": "Stronger phrasing.", "reason": "improve beat", "operator": "editor"},
        )
        assert response.status_code == 200
        _, kwargs = mock_repo.revise_atom.call_args
        assert kwargs.get("reason") == "improve beat" or mock_repo.revise_atom.call_args[1].get("reason") == "improve beat"

    def test_revise_calls_repo_with_correct_atom_id(self, api_client, mock_repo):
        api_client.patch("/v1/atoms/atom-007", json={"text": "New text."})
        mock_repo.revise_atom.assert_called_once()
        call_kwargs = mock_repo.revise_atom.call_args.kwargs
        assert call_kwargs["atom_id"] == "atom-007"


class TestGetAtomRevisions:
    """Tests for ``GET /v1/atoms/{atom_id}/revisions``."""

    def test_returns_200(self, api_client):
        response = api_client.get("/v1/atoms/atom-001/revisions")
        assert response.status_code == 200

    def test_empty_history_returns_empty_list(self, api_client, mock_repo):
        mock_repo.get_atom_revisions.return_value = []
        response = api_client.get("/v1/atoms/atom-001/revisions")
        data = response.json()
        assert data["atom_id"] == "atom-001"
        assert data["revisions"] == []

    def test_revision_history_returned_in_order(self, api_client, mock_repo):
        mock_repo.get_atom_revisions.return_value = [
            {
                "id": "rev-001",
                "atom_id": "atom-001",
                "text": "First revision.",
                "revised_at": "2026-04-26T10:00:00",
                "operator": "user",
                "reason": "",
            },
            {
                "id": "rev-002",
                "atom_id": "atom-001",
                "text": "Second revision.",
                "revised_at": "2026-04-26T11:00:00",
                "operator": "user",
                "reason": "better phrasing",
            },
        ]
        response = api_client.get("/v1/atoms/atom-001/revisions")
        revisions = response.json()["revisions"]
        assert len(revisions) == 2
        assert revisions[0]["id"] == "rev-001"
        assert revisions[1]["text"] == "Second revision."

    def test_revision_record_has_required_fields(self, api_client, mock_repo):
        mock_repo.get_atom_revisions.return_value = [
            {
                "id": "rev-001",
                "atom_id": "atom-001",
                "text": "Some text.",
                "revised_at": "2026-04-26T10:00:00",
                "operator": "user",
                "reason": "",
            }
        ]
        response = api_client.get("/v1/atoms/atom-001/revisions")
        rev = response.json()["revisions"][0]
        for field in ["id", "atom_id", "text", "revised_at", "operator", "reason"]:
            assert field in rev
