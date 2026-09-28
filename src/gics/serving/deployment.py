"""Create a dedicated Pages project, without overwriting an unrelated project."""

import os
import re
import json
from pathlib import Path

import httpx

from gics.data.state import read_json, write_json


def safe_diagnostic(response, secrets):
    """Keep only error diagnostics; never serialize token or project results."""
    try:
        errors = response.json().get('errors', [])
    except (ValueError, AttributeError):
        errors = []
    report = json.dumps({'http':response.status_code,
                         'ray':response.headers.get('cf-ray'),
                         'errors':[{'code':e.get('code'),
                                    'message':str(e.get('message',''))[:400]}
                                   for e in errors if isinstance(e,dict)]})
    for secret in secrets:
        if secret:
            report = report.replace(secret,'[redacted]')
    return report


def diagnose_access(client, account, token, root):
    base = 'https://api.cloudflare.com/client/v4'
    probes = [('account-token',f'{base}/accounts/{account}/tokens/verify'),
              ('user-token',f'{base}/user/tokens/verify'),
              ('pages-list',root)]
    for label, url in probes:
        try:
            response = client.get(url)
            print(f'CF_DIAG {label}: {safe_diagnostic(response,(account,token))}')
            if label == 'pages-list' and response.is_success:
                projects = response.json().get('result',[])
                print(f'CF_DIAG pages-list count: {len(projects)}')
        except (httpx.HTTPError,ValueError,TypeError):
            print(f'CF_DIAG {label}: response unavailable')


def ensure_project(account, token, state_dir, *, transport=None):
    if not account or not token:
        raise RuntimeError("Missing Cloudflare configuration")
    name = "gics-lee851104"
    root = f"https://api.cloudflare.com/client/v4/accounts/{account}/pages/projects"
    marker = state_dir / "project.json"
    with httpx.Client(
        headers={"Authorization": f"Bearer {token}"}, transport=transport, timeout=45
    ) as client:
        response = client.get(f"{root}/{name}")
        phase = "lookup"
        if response.status_code == 404:
            phase = "create"
            response = client.post(
                root,
                json={
                    "name": name,
                    "production_branch": "main",
                    "deployment_configs": {"production": {}, "preview": {}},
                },
            )
            created = True
        else:
            created = False
        if not response.is_success:
            print(f'CF_DIAG {phase}: {safe_diagnostic(response,(account,token))}')
            diagnose_access(client,account,token,root)
            try:
                codes = [
                    str(e["code"])
                    for e in response.json().get("errors", [])
                    if isinstance(e.get("code"), int)
                ]
            except (ValueError, TypeError, KeyError):
                codes = []
            raise RuntimeError(
                f"Cloudflare project {phase} failed (HTTP {response.status_code}; codes {','.join(codes) or 'none'})"
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
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    if not re.fullmatch(r"[0-9a-fA-F]{32}", account):
        raise RuntimeError(
            "CLOUDFLARE_ACCOUNT_ID must contain the 32-character Account ID"
        )
    ensure_project(
        account,
        os.environ.get("CLOUDFLARE_API_TOKEN", "").strip(),
        Path("data/state"),
    )
    print("Dedicated Pages project verified")
