"""Create a dedicated Pages project, without overwriting an unrelated project."""

import os
from pathlib import Path

import httpx

from gics.data.state import read_json, write_json


def ensure_project(account, token, state_dir, *, transport=None):
    if not account or not token:
        raise RuntimeError("Missing Cloudflare configuration")
    name = "sector-rotation"
    root = f"https://api.cloudflare.com/client/v4/accounts/{account}/pages/projects"
    marker = state_dir / "project.json"
    with httpx.Client(
        headers={"Authorization": f"Bearer {token}"}, transport=transport, timeout=45
    ) as client:
        response = client.get(f"{root}/{name}")
        if response.status_code == 404:
            response = client.post(
                root, json={"name": name, "production_branch": "main"}
            )
            created = True
        else:
            created = False
        if not response.is_success:
            raise RuntimeError(
                f"Cloudflare project request failed (HTTP {response.status_code})"
            )
        payload = response.json()
        if not payload.get("success") or not payload.get("result", {}).get("id"):
            raise RuntimeError("Cloudflare project request was unsuccessful")
        project = payload["result"]
        known = read_json(marker)
        if not created and (
            known.get("id") != project["id"] or known.get("account") != account
        ):
            raise RuntimeError(
                "Refusing to deploy to an unrecognized existing Pages project"
            )
        if project.get("production_branch") != "main":
            raise RuntimeError("Unexpected Pages production branch")
        write_json(
            marker,
            {
                "id": project["id"],
                "account": account,
                "name": name,
                "subdomain": project.get("subdomain"),
            },
        )
    return project


if __name__ == "__main__":
    ensure_project(
        os.environ.get("CLOUDFLARE_ACCOUNT_ID"),
        os.environ.get("CLOUDFLARE_API_TOKEN"),
        Path("data/state"),
    )
    print("Dedicated Pages project verified")
