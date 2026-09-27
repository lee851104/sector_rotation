import httpx
import pytest
from gics.serving.deployment import ensure_project
from gics.data.state import read_json, write_json


def test_create_missing_project_and_record_identity(tmp_path):
    def handle(req):
        if req.method == "GET":
            return httpx.Response(404, json={"success": False})
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "id": "ours",
                    "name": "sector-rotation",
                    "production_branch": "main",
                },
            },
        )

    ensure_project("acct", "token", tmp_path, transport=httpx.MockTransport(handle))
    assert read_json(tmp_path / "project.json")["id"] == "ours"


def test_refuses_unrecognized_existing_project(tmp_path):
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200,
            json={
                "success": True,
                "result": {"id": "other", "production_branch": "main"},
            },
        )
    )
    with pytest.raises(RuntimeError, match="unrecognized"):
        ensure_project("acct", "token", tmp_path, transport=transport)


def test_known_project_can_be_redeployed_without_creation(tmp_path):
    write_json(tmp_path / "project.json", {"id": "ours", "account": "acct"})

    def handle(req):
        assert req.method == "GET"
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {"id": "ours", "production_branch": "main"},
            },
        )

    ensure_project("acct", "token", tmp_path, transport=httpx.MockTransport(handle))
