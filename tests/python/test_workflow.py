from pathlib import Path

import yaml


def test_production_updates_are_serialized_and_credentials_stay_server_side():
    workflow = yaml.load(
        Path(".github/workflows/update-deploy.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    assert workflow["concurrency"]["cancel-in-progress"] == "false"
    triggers = workflow["on"]
    assert triggers["schedule"] == [
        {"cron": "17 18 * * 1-5", "timezone": "America/New_York"}
    ]
    assert triggers["workflow_dispatch"]["inputs"]["mode"]["options"] == [
        "smoke",
        "update",
        "deploy",
    ]
    steps = workflow["jobs"]["update"]["steps"]
    assert (
        next(
            s
            for s in steps
            if s.get("name") == "Persist state even after data failures"
        )["if"]
        == "always()"
    )
    assert (
        workflow["jobs"]["update"]["env"]["TWELVE_DATA_API_KEY"]
        == "${{ secrets.TWELVE_DATA_API_KEY }}"
    )
    for file in Path("web").rglob("*"):
        if file.is_file():
            assert "TWELVE_DATA_API_KEY" not in file.read_text(encoding="utf-8")
