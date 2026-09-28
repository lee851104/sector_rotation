import httpx
import json
import pytest
from gics.serving.deployment import ensure_project
from gics.data.state import read_json, write_json


def test_diagnostics_redact_credentials_and_ignore_result():
    from gics.serving.deployment import safe_diagnostic
    response = httpx.Response(500, json={
        'errors':[{'code':8000000,'message':'Failed for sensitive-key account-value'}],
        'result':{'token':'do-not-output'},
    }, headers={'cf-ray':'example-ray'})
    report = safe_diagnostic(response, ('sensitive-key','account-value'))
    assert '8000000' in report and 'Failed for' in report
    assert all(value not in report for value in ('sensitive-key','account-value','do-not-output'))


def test_cloudflare_failure_exposes_code_but_not_raw_message(tmp_path):
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            500, json={"errors": [{"code": 8000000, "message": "secret-value"}]}
        )
    )
    with pytest.raises(RuntimeError, match="lookup failed.*8000000") as error:
        ensure_project("acct", "token", tmp_path, transport=transport)
    assert "secret-value" not in str(error.value)


def test_create_missing_project_and_record_identity(tmp_path):
    def handle(req):
        if req.method == "GET":
            return httpx.Response(404, json={"success": False})
        assert json.loads(req.content)["deployment_configs"] == {
            "production": {},
            "preview": {},
        }
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "id": "ours",
                    "name": "gics-lee851104",
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
