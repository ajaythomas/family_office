import logging
from datetime import date

import yfinance as yf

logger = logging.getLogger(__name__)


def get_price(ticker: str) -> float | None:
    try:
        # always assume US stocks or Canadian tickers if ending in ".TO"
        # international stocks need a suffix like SHOP.TO (in CAD); just SHOP will return the USD price in NYSE
        price = yf.Ticker(ticker).fast_info.last_price
        if price is None or price == 0:
            return None
        return float(price)
    except Exception:
        logger.warning("Could not fetch price for %s", ticker)
        return None


def get_prices(tickers: list[str]) -> dict[str, float | None]:
    return {t: get_price(t) for t in set(tickers)}


def get_earnings_date(ticker: str) -> date | None:
    try:
        cal = yf.Ticker(ticker).calendar
        if not cal:
            return None
        earnings_list = cal.get("Earnings Date", [])
        if not earnings_list:
            return None
        today = date.today()
        for ts in earnings_list:
            d = ts.date() if hasattr(ts, "date") and callable(ts.date) else ts
            if isinstance(d, date) and d >= today:
                return d
        return None
    except Exception:
        logger.warning("Could not fetch earnings date for %s", ticker)
        return None


def get_earnings_dates(tickers: list[str]) -> dict[str, date | None]:
    return {t: get_earnings_date(t) for t in set(tickers)}
