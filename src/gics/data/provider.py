"""Rate-limited Twelve Data client; never include provider error text or URLs in logs."""

import math
import time
from datetime import date, datetime, timezone

import httpx


class ProviderError(RuntimeError):
    pass


class TwelveDataClient:
    def __init__(
        self,
        key,
        budget,
        *,
        base_url="https://api.twelvedata.com",
        transport=None,
        interval=8.7,
        attempts=3,
        sleep=time.sleep,
        clock=time.monotonic,
        now=lambda: datetime.now(timezone.utc),
    ):
        if not key:
            raise ProviderError("Missing TWELVE_DATA_API_KEY")
        self.key, self.budget = key, budget
        self.base_url = base_url.rstrip("/")
        self.http = httpx.Client(transport=transport, timeout=35)
        self.interval, self.attempts, self.sleep, self.clock, self.now = (
            interval,
            attempts,
            sleep,
            clock,
            now,
        )
        self.last_call = None

    def fetch_daily(self, symbol, outputsize=600):
        code = "unavailable"
        for attempt in range(self.attempts):
            if self.last_call is not None:
                self.sleep(max(0, self.interval - (self.clock() - self.last_call)))
            self.budget.reserve(self.now())
            self.last_call = self.clock()
            try:
                response = self.http.get(
                    self.base_url + "/time_series",
                    params={
                        "symbol": symbol,
                        "interval": "1day",
                        "outputsize": outputsize,
                        "adjust": "splits",
                        "apikey": self.key,
                        "order": "asc",
                    },
                )
                code = response.status_code
                payload = response.json() if response.status_code == 200 else {}
                if payload.get("status") == "error":
                    code = int(payload.get("code", 400))
                if code == 200:
                    return self._parse(payload)
                if code != 429 and code < 500:
                    raise ProviderError(
                        f"Provider refused {symbol} (code {code}); check endpoint/plan access"
                    )
            except (httpx.HTTPError, ValueError):
                code = "network_or_json"
            if attempt + 1 < self.attempts:
                self.sleep(65 if code == 429 else 2**attempt)
        raise ProviderError(
            f"Provider failed for {symbol} (code {code}); retry limit reached"
        )

    @staticmethod
    def _parse(payload):
        values = payload.get("values")
        if not isinstance(values, list) or not values:
            raise ProviderError("Provider returned no daily prices")
        result, seen = [], set()
        try:
            for item in values:
                day = date.fromisoformat(item["datetime"]).isoformat()
                close = float(item["close"])
                if day in seen or not math.isfinite(close) or close <= 0:
                    raise ProviderError("Invalid or duplicate daily prices")
                seen.add(day)
                result.append({"date": day, "close": close})
        except (KeyError, TypeError, ValueError):
            raise ProviderError("Invalid daily price format") from None
        return sorted(result, key=lambda p: p["date"])
