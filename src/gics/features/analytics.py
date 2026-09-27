"""Deterministic equal-weight price-return research indices (not official GICS indices)."""

from datetime import datetime, timezone

import numpy as np
import pandas as pd


PERIODS = {"1M": 21, "3M": 63, "6M": 126, "12M": 252}


def finite(value):
    return float(value) if pd.notna(value) and np.isfinite(value) else None


def relative_return(group_return, benchmark_return):
    return (1 + group_return) / (1 + benchmark_return) - 1


def quadrant(x, y):
    return (
        ("leading" if y >= 100 else "weakening")
        if x >= 100
        else ("improving" if y >= 100 else "lagging")
    )


def group_index(frame):
    returns = frame.pct_change(fill_method=None)
    counts = returns.count(axis=1)
    daily = returns.mean(axis=1)
    result = pd.Series(np.nan, index=frame.index)
    current = None
    for i in range(len(frame)):
        if i == 0 and frame.iloc[i].notna().any():
            current = 100.0
            result.iloc[i] = current
        elif pd.notna(daily.iloc[i]):
            current = (current if current is not None else 100.0) * (1 + daily.iloc[i])
            result.iloc[i] = current
        else:
            current = None
    return result, counts


def period_return(series, days):
    if len(series) <= days:
        return None
    window = series.iloc[-days - 1 :]
    if window.isna().any():
        return None
    return finite(window.iloc[-1] / window.iloc[0] - 1)


def build_dataset(
    universe,
    prices,
    quality,
    *,
    benchmark="SPY",
    periods=None,
    rs_weeks=10,
    momentum_weeks=4,
):
    periods = periods or PERIODS
    as_of = quality["as_of"]
    series = {
        s: pd.Series(
            {p["date"]: p["close"] for p in bars if p["date"] <= as_of}, dtype=float
        )
        for s, bars in prices.items()
    }
    bench = series[benchmark].sort_index()
    bench.index = pd.to_datetime(bench.index)
    frame = pd.DataFrame(
        {s: v.rename(index=pd.to_datetime) for s, v in series.items()}
    ).reindex(bench.index)
    valid = set(quality["valid"])
    groups = []
    for level in ("L1", "L2", "L3", "L4"):
        classifications = {
            m["gics"][level]["code"]: m["gics"][level]
            for m in universe
            if m["gics"][level]
        }
        for code, classification in sorted(classifications.items()):
            members = [
                m
                for m in universe
                if m["gics"][level] and m["gics"][level]["code"] == code
            ]
            available = [
                m["symbol"]
                for m in members
                if m["symbol"] in frame and m["symbol"] in valid
            ]
            index, counts = group_index(frame[available])
            q = index / bench
            # A restarted index has a new base. Never compare across its last gap,
            # even when that gap disappears in end-of-week downsampling.
            gaps = np.flatnonzero(q.isna().to_numpy())
            if len(gaps):
                q = q.iloc[gaps[-1] + 1 :]
            # Preserve missing values at each week's actual last benchmark session.
            weekly = q.groupby(q.index.to_period("W-FRI")).agg(lambda x: x.iloc[-1])
            dates = q.groupby(q.index.to_period("W-FRI")).apply(
                lambda x: x.index[-1].date().isoformat()
            )
            ratio = 100 * weekly / weekly.rolling(rs_weeks, min_periods=rs_weeks).mean()
            momentum = (
                100
                * ratio
                / ratio.rolling(momentum_weeks, min_periods=momentum_weeks).mean()
            )
            rotation = [
                {
                    "date": dates.loc[d],
                    "x": float(ratio.loc[d]),
                    "y": float(momentum.loc[d]),
                    "quadrant": quadrant(ratio.loc[d], momentum.loc[d]),
                }
                for d in weekly.index
                if finite(ratio.loc[d]) is not None
                and finite(momentum.loc[d]) is not None
            ]
            metrics = {}
            for label, days in periods.items():
                ret, br = period_return(index, days), period_return(bench, days)
                stock_returns = [
                    {
                        "symbol": m["symbol"],
                        "name": m["name"],
                        "return": period_return(frame[m["symbol"]], days)
                        if m["symbol"] in available
                        else None,
                    }
                    for m in members
                ]
                values = [r["return"] for r in stock_returns if r["return"] is not None]
                stock_returns.sort(
                    key=lambda r: (r["return"] is None, -(r["return"] or 0))
                )
                metrics[label] = {
                    "return": ret,
                    "rs": relative_return(ret, br)
                    if ret is not None and br is not None
                    else None,
                    "breadth": sum(v > 0 for v in values) / len(values)
                    if values
                    else None,
                    "breadth_count": len(values),
                    "stocks": stock_returns,
                }
            groups.append(
                {
                    "id": f"{level}:{code}",
                    "level": level,
                    "code": code,
                    "name": classification["name"],
                    "sector_code": members[0]["gics"]["L1"]["code"],
                    "member_count": len(members),
                    "valid_count": len(available),
                    "periods": metrics,
                    "index": [
                        {
                            "date": d.date().isoformat(),
                            "value": finite(index.loc[d]),
                            "count": int(counts.loc[d]),
                        }
                        for d in index.index
                    ],
                    "rotation": rotation,
                }
            )
    return {
        "schema_version": 1,
        "as_of": as_of,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Twelve Data",
        "benchmark": benchmark,
        "methodology": "equal_weight_price_return",
        "coverage": {
            "prices": quality["ratio"],
            "valid": len(valid),
            "total": len(universe),
            "classification": {
                level: sum(m["gics"][level] is not None for m in universe)
                / len(universe)
                for level in ("L1", "L2", "L3", "L4")
            },
        },
        "missing_symbols": quality["missing"],
        "groups": groups,
        "benchmark_series": [
            {"date": d.date().isoformat(), "value": float(v)} for d, v in bench.items()
        ],
    }
