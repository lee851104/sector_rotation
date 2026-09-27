"""Validate complete bars and refuse materially incomplete publication."""

import math
from datetime import date
from zoneinfo import ZoneInfo


class QualityError(RuntimeError):
    pass


def complete_bars(bars, now):
    local = now.astimezone(ZoneInfo("America/New_York"))
    cutoff = local.date().isoformat()
    closed = local.hour >= 16
    result, seen = [], set()
    for bar in bars:
        day = date.fromisoformat(bar["date"]).isoformat()
        close = float(bar["close"])
        if day in seen or not math.isfinite(close) or close <= 0:
            raise QualityError("Invalid daily bars")
        seen.add(day)
        if day < cutoff or (day == cutoff and closed):
            result.append({"date": day, "close": close})
    return sorted(result, key=lambda p: p["date"])


def anomalous_history(bars, extreme):
    return any(
        abs(b["close"] / a["close"] - 1) > extreme for a, b in zip(bars, bars[1:])
    )


def validate_snapshot(
    universe,
    prices,
    now,
    previous_as_of=None,
    *,
    benchmark="SPY",
    threshold=0.98,
    extreme=0.8,
    minimum_history=600,
):
    clean = {s: complete_bars(b, now) for s, b in prices.items()}
    reference = clean.get(benchmark, [])
    if not reference:
        raise QualityError("Missing benchmark")
    if len(reference) < minimum_history:
        raise QualityError("Insufficient benchmark history")
    if anomalous_history(reference, extreme):
        raise QualityError("Benchmark adjustment anomaly")
    as_of = reference[-1]["date"]
    if previous_as_of and as_of < previous_as_of:
        raise QualityError("Benchmark date regressed")
    valid, missing = [], []
    for member in universe:
        symbol = member["symbol"]
        bars = clean.get(symbol, [])
        anomalous = anomalous_history(bars, extreme)
        if bars and bars[-1]["date"] == as_of and not anomalous:
            valid.append(symbol)
        else:
            missing.append(symbol)
    ratio = len(valid) / len(universe) if universe else 0
    if ratio < threshold:
        raise QualityError(
            f"Latest-day coverage {len(valid)}/{len(universe)} below {threshold:.0%}"
        )
    return {
        "as_of": as_of,
        "valid": valid,
        "missing": missing,
        "ratio": ratio,
        "no_new_data": as_of == previous_as_of,
    }
