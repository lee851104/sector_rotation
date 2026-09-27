import copy
from datetime import datetime, timezone

import pytest

from gics.data.state import read_json, write_json
from gics.serving.pipeline import run_update


UNIVERSE = [
    {
        "symbol": "A",
        "name": "A",
        "provider_symbol": "A",
        "gics": {
            f"L{i}": {"code": "45" + "10" * (i - 1), "name": "Tech"}
            for i in range(1, 5)
        },
    }
]
NOW = datetime(2026, 9, 25, 23, tzinfo=timezone.utc)
CONFIG = {
    "provider": {"outputsize": 600},
    "analytics": {
        "benchmark": "SPY",
        "minimum_benchmark_bars": 2,
        "minimum_coverage": 0.98,
        "extreme_daily_return": 0.8,
        "periods": {"1M": 21},
        "rs_weeks": 10,
        "momentum_weeks": 4,
    },
}


class Provider:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def fetch_daily(self, symbol, outputsize=600):
        self.calls.append(symbol)
        if self.fail and symbol == "A":
            raise RuntimeError("temporary test error")
        return [
            {"date": "2026-09-24", "close": 100.0},
            {"date": "2026-09-25", "close": 101.0},
        ]


def test_update_and_same_day_dedup(tmp_path):
    p = Provider()
    out = tmp_path / "dashboard.json"
    run_update(UNIVERSE, p, tmp_path / "state", out, CONFIG, now=NOW)
    assert read_json(out)["as_of"] == "2026-09-25"
    before = out.read_bytes()
    assert (
        run_update(UNIVERSE, p, tmp_path / "state", out, CONFIG, now=NOW)
        == "already_updated"
    )
    assert p.calls == ["SPY", "A"]
    assert out.read_bytes() == before


def test_failed_update_preserves_prior_output_and_resumes(tmp_path):
    out = tmp_path / "dashboard.json"
    write_json(out, {"as_of": "2026-09-24"})
    before = out.read_bytes()
    with pytest.raises(Exception):
        run_update(UNIVERSE, Provider(True), tmp_path / "state", out, CONFIG, now=NOW)
    assert out.read_bytes() == before
    p = Provider()
    run_update(UNIVERSE, p, tmp_path / "state", out, CONFIG, now=NOW)
    assert p.calls == ["A"]
    assert read_json(out)["as_of"] == "2026-09-25"


def test_no_new_data_preserves_market_date(tmp_path):
    out = tmp_path / "dashboard.json"
    run_update(UNIVERSE, Provider(), tmp_path / "state", out, CONFIG, now=NOW)
    before = copy.deepcopy(read_json(out))
    next_day = datetime(2026, 9, 26, 23, tzinfo=timezone.utc)
    result = run_update(
        UNIVERSE, Provider(), tmp_path / "state", out, CONFIG, now=next_day
    )
    assert result == "no_new_data"
    assert read_json(out) == before


def test_stale_member_cache_is_refetched(tmp_path):
    class StaleProvider(Provider):
        def fetch_daily(self, symbol, outputsize=600):
            result = super().fetch_daily(symbol, outputsize)
            return result[:-1] if symbol == "A" else result

    out = tmp_path / "dashboard.json"
    with pytest.raises(Exception):
        run_update(UNIVERSE, StaleProvider(), tmp_path / "state", out, CONFIG, now=NOW)
    corrected = Provider()
    assert (
        run_update(UNIVERSE, corrected, tmp_path / "state", out, CONFIG, now=NOW)
        == "success"
    )
    assert corrected.calls == ["A"]


def test_delayed_benchmark_does_not_lock_session(tmp_path):
    class DelayedProvider(Provider):
        def fetch_daily(self, symbol, outputsize=600):
            self.calls.append(symbol)
            return [
                {"date": "2026-09-23", "close": 100},
                {"date": "2026-09-24", "close": 101},
            ]

    out = tmp_path / "dashboard.json"
    run_update(UNIVERSE, DelayedProvider(), tmp_path / "state", out, CONFIG, now=NOW)
    corrected = Provider()
    assert (
        run_update(UNIVERSE, corrected, tmp_path / "state", out, CONFIG, now=NOW)
        == "success"
    )
    assert read_json(out)["as_of"] == "2026-09-25"
    assert corrected.calls == ["SPY", "A"]


def test_checkpoints_count_new_attempts_on_resume(tmp_path):
    import hashlib

    members = [
        dict(UNIVERSE[0], symbol=f"A{i}", provider_symbol=f"A{i}") for i in range(24)
    ]
    signature = hashlib.sha256(
        ",".join(sorted(m["symbol"] for m in members)).encode()
    ).hexdigest()
    cached = {f"A{i}": Provider().fetch_daily("A") for i in (3, 8, 13, 18, 23)}
    cached["SPY"] = Provider().fetch_daily("SPY")
    state = tmp_path / "state"
    write_json(
        state / "batch.json",
        {
            "id": f"2026-09-25:{signature[:12]}",
            "prices": cached,
            "failures": {},
            "complete": False,
        },
    )
    provider = Provider()
    counts = []

    def checkpoint():
        counts.append(len(provider.calls))
        assert read_json(state / "status.json")["state"] in ("running", "success")

    run_update(
        members,
        provider,
        state,
        tmp_path / "dashboard.json",
        CONFIG,
        now=NOW,
        checkpoint=checkpoint,
    )
    assert counts[0] == 0
    assert max(b - a for a, b in zip(counts, counts[1:])) <= 5


def test_crash_allowance_is_persisted_before_next_request(tmp_path):
    from gics.serving.pipeline import start_run
    from gics.data.state import Budget

    write_json(tmp_path / "status.json", {"state": "running"})
    write_json(tmp_path / "budget.json", {"day": "2026-09-25", "used": 100})
    observations = []

    def checkpoint():
        observations.append(
            (
                read_json(tmp_path / "status.json")["state"],
                read_json(tmp_path / "budget.json")["used"],
            )
        )

    start_run(
        tmp_path, Budget(tmp_path / "budget.json"), checkpoint, now=NOW, recover=True
    )
    assert observations == [("running", 120)]
