"""Build a complete candidate snapshot before publishing. Secrets are environment-only."""

import argparse
import hashlib
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import yaml

from gics.data.provider import TwelveDataClient, ProviderError
from gics.data.quality import (
    complete_bars,
    validate_snapshot,
    anomalous_history,
    QualityError,
)
from gics.data.state import Budget, BudgetExceeded, read_json, write_json
from gics.data.universe import load_structure, parse_constituents
from gics.features.analytics import build_dataset


def load_universe(config, state_dir, *, http=None):
    structure = load_structure(Path("configs/gics_structure.json"))
    client = http or httpx.Client(
        timeout=30,
        follow_redirects=True,
        headers={
            "User-Agent": "GICSDashboard/0.1 (research; daily membership refresh)"
        },
    )
    snapshot_path = state_dir / "universe.json"
    for field, csv in [("url", False), ("fallback_url", True)]:
        try:
            response = client.get(config[field])
            response.raise_for_status()
            members = parse_constituents(response.text, structure, csv=csv)
            if (
                not config["minimum_members"]
                <= len(members)
                <= config["maximum_members"]
            ):
                raise ValueError("Unexpected membership count")
            snapshot = {
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "source": config[field],
                "members": members,
            }
            write_json(snapshot_path, snapshot)
            return snapshot
        except (httpx.HTTPError, ValueError):
            continue
    snapshot = read_json(snapshot_path)
    if snapshot and datetime.now(timezone.utc) - datetime.fromisoformat(
        snapshot["retrieved_at"]
    ) <= timedelta(days=config["max_snapshot_age_days"]):
        return snapshot
    raise RuntimeError("Cannot obtain a recent valid membership list")


def session_key(now):
    local = now.astimezone(ZoneInfo("America/New_York"))
    return (
        local.date() if local.hour >= 16 else local.date() - timedelta(days=1)
    ).isoformat()


def persist_remote():
    # Only a trusted workflow enables this fixed command. Never run a command from data.
    if os.environ.get("GICS_PERSIST_STATE") == "1":
        subprocess.run(
            ["bash", "scripts/persist-state.sh"], check=True, stdout=subprocess.DEVNULL
        )


def start_run(state_dir, budget, checkpoint, *, now=None, recover=False):
    now = now or datetime.now(timezone.utc)
    if recover and read_json(state_dir / "status.json").get("state") == "running":
        saved = read_json(budget.path)
        if saved.get("day") == now.date().isoformat():
            saved["used"] += 20
            write_json(budget.path, saved)
    write_json(
        state_dir / "status.json", {"state": "running", "updated_at": now.isoformat()}
    )
    checkpoint()


def run_update(
    universe, provider, state_dir, output, config, *, now=None, checkpoint=None
):
    now = now or datetime.now(timezone.utc)
    state_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = checkpoint or (lambda: None)
    signature = hashlib.sha256(
        ",".join(sorted(m["symbol"] for m in universe)).encode()
    ).hexdigest()
    batch_id = f"{session_key(now)}:{signature[:12]}"
    state_path = state_dir / "batch.json"
    batch = read_json(state_path)
    previous = read_json(output)
    status_path = state_dir / "status.json"
    if (
        batch.get("id") == batch_id
        and batch.get("complete")
        and previous.get("as_of", "") >= session_key(now)
    ):
        write_json(
            status_path,
            {
                "state": "already_updated",
                "as_of": previous["as_of"],
                "updated_at": now.isoformat(),
            },
        )
        checkpoint()
        return "already_updated"
    if batch.get("id") != batch_id:
        batch = {"id": batch_id, "prices": {}, "failures": {}, "complete": False}
    benchmark = config["analytics"]["benchmark"]
    symbols = [(benchmark, benchmark)] + [
        (m["symbol"], m["provider_symbol"])
        for m in universe
        if m["symbol"] != benchmark
    ]
    write_json(
        status_path,
        {
            "state": "running",
            "completed": len(batch["prices"]),
            "total": len(symbols),
            "updated_at": now.isoformat(),
        },
    )
    checkpoint()
    attempted = 0
    try:
        for symbol, provider_symbol in symbols:
            if symbol in batch["prices"]:
                cached = complete_bars(batch["prices"][symbol], now)
                reference = complete_bars(batch["prices"].get(benchmark, []), now)
                required_date = (
                    session_key(now)
                    if symbol == benchmark
                    else (reference[-1]["date"] if reference else session_key(now))
                )
                if (
                    cached
                    and cached[-1]["date"] >= required_date
                    and not anomalous_history(
                        cached, config["analytics"]["extreme_daily_return"]
                    )
                ):
                    continue
                del batch["prices"][symbol]
            try:
                bars = provider.fetch_daily(
                    provider_symbol, config["provider"]["outputsize"]
                )
                batch["prices"][symbol] = bars
                batch["failures"].pop(symbol, None)
            except BudgetExceeded:
                raise
            except (ProviderError, RuntimeError) as error:
                # Controlled text only; never persist third-party error messages.
                batch["failures"][symbol] = type(error).__name__
                if symbol == benchmark:
                    raise
            write_json(state_path, batch)
            write_json(
                status_path,
                {
                    "state": "running",
                    "completed": len(batch["prices"]),
                    "total": len(symbols),
                    "failed": len(batch["failures"]),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            attempted += 1
            if attempted % 5 == 0:
                checkpoint()
        prices = {s: complete_bars(b, now) for s, b in batch["prices"].items()}
        opts = config["analytics"]
        quality = validate_snapshot(
            universe,
            prices,
            now,
            previous.get("as_of"),
            benchmark=benchmark,
            threshold=opts["minimum_coverage"],
            extreme=opts["extreme_daily_return"],
            minimum_history=opts.get("minimum_benchmark_bars", 600),
        )
        outcome = "no_new_data" if quality["no_new_data"] else "success"
        if outcome == "success":
            dataset = build_dataset(
                universe,
                prices,
                quality,
                benchmark=benchmark,
                periods=opts["periods"],
                rs_weeks=opts["rs_weeks"],
                momentum_weeks=opts["momentum_weeks"],
            )
            membership = read_json(state_dir / "universe.json")
            dataset["universe_source"] = {
                k: membership[k] for k in ("source", "retrieved_at") if k in membership
            }
            dataset["structure_source"] = read_json(
                Path("configs/gics_structure.json")
            ).get("source")
            write_json(output, dataset)
        batch["complete"] = quality["as_of"] >= session_key(now)
        write_json(state_path, batch)
        write_json(
            status_path,
            {
                "state": outcome,
                "as_of": quality["as_of"],
                "completed": len(batch["prices"]),
                "total": len(symbols),
                "failed": len(batch["failures"]),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        checkpoint()
        return outcome
    except Exception as error:
        write_json(state_path, batch)
        write_json(
            status_path,
            {
                "state": "quota_exhausted"
                if isinstance(error, BudgetExceeded)
                else "failed",
                "completed": len(batch["prices"]),
                "total": len(symbols),
                "error": type(error).__name__,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        checkpoint()
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/dashboard.yaml")
    parser.add_argument("--state-dir", type=Path, default=Path("data/state"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/state/dashboard.json")
    )
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    global _active_state_dir
    _active_state_dir = args.state_dir
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    budget = Budget(
        args.state_dir / "budget.json",
        config["provider"]["daily_credits"],
        config["provider"]["reserve_credits"],
    )
    provider = TwelveDataClient(
        os.environ.get("TWELVE_DATA_API_KEY", ""),
        budget,
        base_url=config["provider"]["base_url"],
        interval=config["provider"]["interval_seconds"],
        attempts=config["provider"]["attempts"],
    )
    args.state_dir.mkdir(parents=True, exist_ok=True)
    # Save the running marker and any crash allowance before even the first request.
    start_run(
        args.state_dir,
        budget,
        persist_remote,
        recover=os.environ.get("GICS_PERSIST_STATE") == "1",
    )
    if args.smoke:
        report = []
        for symbol in ("SPY", "AAPL", "MSFT", "BRK.B"):
            bars = provider.fetch_daily(symbol, config["provider"]["outputsize"])
            if len(bars) < config["provider"]["outputsize"]:
                raise ProviderError(
                    f"{symbol}: insufficient historical coverage ({len(bars)} bars)"
                )
            report.append(
                {
                    "symbol": symbol,
                    "bars": len(bars),
                    "first": bars[0]["date"],
                    "last": bars[-1]["date"],
                }
            )
        write_json(
            args.state_dir / "smoke.json",
            {
                "version": 1,
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "symbols": report,
            },
        )
        write_json(
            args.state_dir / "status.json",
            {
                "state": "smoke_success",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        persist_remote()
        print(
            "Live provider smoke passed: "
            + ", ".join(f"{r['symbol']} {r['bars']} bars" for r in report)
        )
    else:
        if not read_json(args.state_dir / "smoke.json").get("verified_at"):
            raise ProviderError("Run the smoke workflow before the full update")
        snapshot = load_universe(config["universe"], args.state_dir)
        outcome = run_update(
            snapshot["members"],
            provider,
            args.state_dir,
            args.output,
            config,
            checkpoint=persist_remote,
        )
        print(f"Update result: {outcome}")
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
                f.write(f"outcome={outcome}\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Avoid serializing request exceptions (URLs may carry credentials).
        state_dir = globals().get("_active_state_dir")
        if state_dir and read_json(state_dir / "status.json").get("state") == "running":
            write_json(
                state_dir / "status.json",
                {
                    "state": "quota_exhausted"
                    if isinstance(error, BudgetExceeded)
                    else "failed",
                    "error": type(error).__name__,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            persist_remote()
        # These exception classes contain only messages created by our code.
        detail = (
            str(error)
            if isinstance(error, (ProviderError, QualityError, BudgetExceeded))
            else "Check workflow configuration"
        )
        print(f"Update stopped: {type(error).__name__}. {detail}", file=sys.stderr)
        sys.exit(1)
