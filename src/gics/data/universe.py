"""Read public membership and map only exact GICS names."""

import json
import re
from io import StringIO
from pathlib import Path

import pandas as pd


def normalize(value: str) -> str:
    return " ".join(str(value).replace("\xa0", " ").split()).casefold()


def load_structure(path: Path) -> dict:
    structure = json.loads(path.read_text(encoding="utf-8"))
    for item in structure["entries"]:
        if any(
            not item["code"].startswith(item[level]["code"])
            for level in ("sector", "group", "industry")
        ):
            raise ValueError("GICS parent/code mismatch")
    return structure


def parse_constituents(
    content: str, structure: dict, *, csv: bool = False
) -> list[dict]:
    tables = (
        [pd.read_csv(StringIO(content))] if csv else pd.read_html(StringIO(content))
    )
    frame = next((t for t in tables if "GICS Sub-Industry" in t.columns), None)
    required = ["Symbol", "Security", "GICS Sector", "GICS Sub-Industry"]
    if frame is None or not set(required).issubset(frame.columns):
        raise ValueError("Membership source missing required columns")
    entries = {normalize(e["name"]): e for e in structure["entries"]}
    sectors = {
        normalize(e["sector"]["name"]): e["sector"] for e in structure["entries"]
    }
    result, seen = [], set()
    for _, row in frame.iterrows():
        symbol = str(row["Symbol"]).strip()
        if not re.fullmatch(r"[A-Z0-9.\-]{1,15}", symbol):
            raise ValueError("Invalid symbol in membership source")
        if symbol in seen:
            raise ValueError(f"duplicate symbol: {symbol}")
        seen.add(symbol)
        sector = sectors.get(normalize(row["GICS Sector"]))
        entry = entries.get(normalize(row["GICS Sub-Industry"]))
        if entry and sector and entry["sector"]["code"] != sector["code"]:
            raise ValueError(f"Classification conflict: {symbol}")
        result.append(
            {
                "symbol": symbol,
                "provider_symbol": symbol,
                "name": str(row["Security"]),
                "gics": {
                    "L1": sector,
                    "L2": entry["group"] if entry else None,
                    "L3": entry["industry"] if entry else None,
                    "L4": {"code": entry["code"], "name": entry["name"]}
                    if entry
                    else None,
                },
            }
        )
    return result
