import logging

import yfinance as yf

logger = logging.getLogger(__name__)


def get_price(ticker: str) -> float | None:
    try:
        # always assume US stocks
        # international stocks need a suffix like SHOP.TO (in CAD); just SHOP will return the USD price in NYSE
        # TODO: gotta do something about this
        price = yf.Ticker(ticker).fast_info.last_price
        if price is None or price == 0:
            return None
        return float(price)
    except Exception:
        logger.warning("Could not fetch price for %s", ticker)
        return None


def get_prices(tickers: list[str]) -> dict[str, float | None]:
    return {t: get_price(t) for t in set(tickers)}
