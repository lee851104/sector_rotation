import pytest

from gics.data.universe import parse_constituents


STRUCTURE = {
    "entries": [
        {
            "code": "40201020",
            "name": "Multi-Sector Holdings",
            "sector": {"code": "40", "name": "Financials"},
            "group": {"code": "4020", "name": "Financial Services"},
            "industry": {"code": "402010", "name": "Financial Services"},
        }
    ]
}


def table(rows):
    return (
        "<table><tr><th>Symbol</th><th>Security</th><th>GICS Sector</th><th>GICS Sub-Industry</th></tr>"
        + "".join(
            "<tr>" + "".join(f"<td>{x}</td>" for x in row) + "</tr>" for row in rows
        )
        + "</table>"
    )


def test_multishare_class_and_precise_mapping():
    rows = parse_constituents(
        table([["BRK.B", "Berkshire", "Financials", "Multi-Sector Holdings"]]),
        STRUCTURE,
    )
    assert rows[0]["symbol"] == "BRK.B"
    assert rows[0]["provider_symbol"] == "BRK.B"
    assert rows[0]["gics"]["L4"]["code"] == "40201020"
    assert rows[0]["gics"]["L1"]["code"] == "40"


def test_unknown_industry_is_not_guessed():
    row = parse_constituents(
        table([["X", "Unknown", "Financials", "Something New"]]), STRUCTURE
    )[0]
    assert row["gics"]["L4"] is None
    assert row["gics"]["L1"]["code"] == "40"


def test_duplicate_symbols_rejected():
    row = ["A", "A", "Financials", "Multi-Sector Holdings"]
    with pytest.raises(ValueError, match="duplicate"):
        parse_constituents(table([row, row]), STRUCTURE)


def test_missing_columns_rejected():
    with pytest.raises(ValueError):
        parse_constituents(
            "<table><tr><th>Symbol</th></tr><tr><td>A</td></tr></table>", STRUCTURE
        )
