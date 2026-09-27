from datetime import datetime, timezone

import httpx
import pytest

from gics.data.provider import TwelveDataClient, ProviderError
from gics.data.state import Budget, BudgetExceeded, read_json, write_json


def test_atomic_state_and_budget_persist(tmp_path):
    path = tmp_path / "state.json"
    budget = Budget(path, limit=2, reserve=0)
    now = datetime(2026, 9, 25, tzinfo=timezone.utc)
    budget.reserve(now)
    Budget(path, limit=2, reserve=0).reserve(now)
    with pytest.raises(BudgetExceeded):
        budget.reserve(now)
    budget.reserve(datetime(2026, 9, 26, tzinfo=timezone.utc))
    assert read_json(path)["used"] == 1
    before = path.read_bytes()
    with pytest.raises(ValueError):
        write_json(path, {"bad": float("nan")})
    assert path.read_bytes() == before


def client(tmp_path, handler, **kwargs):
    return TwelveDataClient(
        "do-not-log-this-key",
        Budget(tmp_path / "budget.json"),
        transport=httpx.MockTransport(handler),
        interval=0,
        sleep=lambda _: None,
        **kwargs,
    )


def test_success_sort_dates_and_parameters(tmp_path):
    def handle(request):
        assert request.url.params["symbol"] == "BRK.B"
        assert request.url.params["outputsize"] == "600"
        assert request.url.params["adjust"] == "splits"
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "values": [
                    {"datetime": "2026-09-25", "close": "101"},
                    {"datetime": "2026-09-24", "close": "100"},
                ],
            },
        )

    assert client(tmp_path, handle).fetch_daily("BRK.B")[0] == {
        "date": "2026-09-24",
        "close": 100.0,
    }


def test_rate_limit_retry_is_bounded_and_counted(tmp_path):
    c = client(tmp_path, lambda _: httpx.Response(429))
    with pytest.raises(ProviderError, match="429"):
        c.fetch_daily("AAPL")
    assert read_json(tmp_path / "budget.json")["used"] == 3


def test_error_response_does_not_leak_key_or_retry_permissions(tmp_path):
    c = client(
        tmp_path,
        lambda _: httpx.Response(
            200, json={"status": "error", "code": 403, "message": "do-not-log-this-key"}
        ),
    )
    with pytest.raises(ProviderError) as exc:
        c.fetch_daily("AAPL")
    assert "do-not-log" not in str(exc.value)
    assert read_json(tmp_path / "budget.json")["used"] == 1


@pytest.mark.parametrize(
    "values",
    [
        [],
        [{"datetime": "2026-09-25", "close": "nan"}],
        [{"datetime": "2026-09-25", "close": "0"}],
        [{"datetime": "not-a-date", "close": "100"}],
        [{"datetime": "2026-09-25", "close": "100"}] * 2,
    ],
)
def test_invalid_prices_rejected(tmp_path, values):
    with pytest.raises(ProviderError):
        client(
            tmp_path, lambda _: httpx.Response(200, json={"values": values})
        ).fetch_daily("AAPL")


def test_timeout_redacts_request_url(tmp_path):
    def handle(request):
        raise httpx.ReadTimeout(str(request.url))

    with pytest.raises(ProviderError) as exc:
        client(tmp_path, handle).fetch_daily("AAPL")
    assert "apikey" not in str(exc.value)


def test_missing_key_does_not_make_request(tmp_path):
    with pytest.raises(ProviderError, match="TWELVE_DATA_API_KEY"):
        TwelveDataClient("", Budget(tmp_path / "budget.json"))
