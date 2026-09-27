from datetime import datetime, timezone
from gics.data.quality import complete_bars


def test_future_and_unclosed_prices_do_not_enter_snapshot():
    rows = [
        {"date": "2026-09-24", "close": 100},
        {"date": "2026-09-25", "close": 110},
        {"date": "2026-09-28", "close": 200},
    ]
    result = complete_bars(rows, datetime(2026, 9, 25, 18, tzinfo=timezone.utc))
    assert result == [{"date": "2026-09-24", "close": 100.0}]
