from datetime import datetime, timezone

import pandas as pd
import pytest

from gics.features.analytics import (
    relative_return,
    quadrant,
    group_index,
    build_dataset,
)
from gics.data.quality import validate_snapshot, QualityError


def bars(values, start="2024-01-01"):
    return [
        {"date": d.date().isoformat(), "close": float(v)}
        for d, v in zip(pd.bdate_range(start, periods=len(values)), values)
    ]


def member(symbol="A"):
    return {
        "symbol": symbol,
        "name": symbol,
        "provider_symbol": symbol,
        "gics": {
            f"L{i}": {"code": "45" + "10" * (i - 1), "name": "Technology"}
            for i in range(1, 5)
        },
    }


def test_relative_return_is_a_ratio_not_percentage_subtraction():
    assert relative_return(0.10, 0.05) == pytest.approx(1.10 / 1.05 - 1)


@pytest.mark.parametrize(
    "x,y,q",
    [
        (100, 100, "leading"),
        (99, 101, "improving"),
        (99, 99, "lagging"),
        (101, 99, "weakening"),
    ],
)
def test_quadrant_boundaries(x, y, q):
    assert quadrant(x, y) == q


def test_compounding_and_daily_rebalancing():
    frame = pd.DataFrame({"A": [100, 110, 99], "B": [100, 100, 100]})
    idx, counts = group_index(frame)
    assert idx.iloc[-1] == pytest.approx(99.75)
    assert counts.tolist() == [0, 2, 2]


def test_missing_price_is_not_forward_filled():
    idx, counts = group_index(pd.DataFrame({"A": [100, None, 110]}))
    assert pd.isna(idx.iloc[-1])
    assert counts.tolist() == [0, 0, 0]


def test_dataset_breadth_short_history_and_rs():
    data = {
        "SPY": bars([100] * 30),
        "A": bars(list(range(100, 130))),
        "B": bars([100] * 30),
    }
    quality = {
        "as_of": data["SPY"][-1]["date"],
        "valid": ["A", "B"],
        "missing": [],
        "ratio": 1.0,
    }
    out = build_dataset([member("A"), member("B")], data, quality)
    group = out["groups"][0]
    assert group["periods"]["12M"]["rs"] is None
    assert group["periods"]["1M"]["breadth"] == 0.5
    assert group["periods"]["1M"]["breadth_count"] == 2
    assert group["rotation"] == []
    assert out["schema_version"] == 1


def test_rotation_warmup_and_constant_relative_performance():
    data = {"SPY": bars([100] * 400), "A": bars([50] * 400)}
    q = {"as_of": data["SPY"][-1]["date"], "valid": ["A"], "missing": [], "ratio": 1.0}
    rotation = build_dataset([member()], data, q)["groups"][0]["rotation"]
    assert rotation[0]["x"] == 100
    assert rotation[0]["y"] == 100
    assert len(rotation) > 52


def test_98_percent_coverage_accepts_and_stale_member_is_missing():
    universe = [member(f"A{i}") for i in range(100)]
    data = {"SPY": bars([100, 100]), **{f"A{i}": bars([100, 100]) for i in range(98)}}
    data["A98"] = bars([100])
    now = datetime(2024, 1, 3, 23, tzinfo=timezone.utc)
    assert validate_snapshot(universe, data, now, minimum_history=1)["ratio"] == 0.98
    del data["A97"]
    with pytest.raises(QualityError, match="coverage"):
        validate_snapshot(universe, data, now, minimum_history=1)


def test_unclosed_bar_and_benchmark_regression_rejected():
    data = {"SPY": bars([100, 100]), "A": bars([100, 100])}
    q = validate_snapshot(
        [member()],
        data,
        datetime(2024, 1, 2, 15, tzinfo=timezone.utc),
        minimum_history=1,
    )
    assert q["as_of"] == "2024-01-01"
    with pytest.raises(QualityError, match="regressed"):
        validate_snapshot(
            [member()],
            data,
            datetime(2024, 1, 3, 23, tzinfo=timezone.utc),
            "2024-01-03",
            minimum_history=1,
        )


def test_recent_gap_restarts_rotation_warmup():
    data = {"SPY": bars([100] * 100), "A": bars([100 * 1.01**i for i in range(100)])}
    del data["A"][91]
    quality = {
        "as_of": data["SPY"][-1]["date"],
        "valid": ["A"],
        "missing": [],
        "ratio": 1,
    }
    assert build_dataset([member()], data, quality)["groups"][0]["rotation"] == []


def test_benchmark_requires_usable_history():
    data = {"SPY": bars([100]), "A": bars([100])}
    with pytest.raises(QualityError, match="history"):
        validate_snapshot(
            [member()], data, datetime(2024, 1, 3, 23, tzinfo=timezone.utc)
        )


@pytest.mark.parametrize("symbol", ["SPY", "A"])
def test_historical_adjustment_break_is_rejected(symbol):
    data = {"SPY": bars([100] * 4), "A": bars([100] * 4)}
    data[symbol] = bars([100, 10, 10, 10])
    with pytest.raises(QualityError):
        validate_snapshot(
            [member()],
            data,
            datetime(2024, 1, 8, 23, tzinfo=timezone.utc),
            minimum_history=1,
        )
