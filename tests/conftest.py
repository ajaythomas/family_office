from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from typing import Generator

from app.config import settings
from app.database import get_db
from app.models import Base
from main import app

_engine = create_engine(settings.database_url_test)

'''
@pytest.fixture marks a function as a fixture — a piece of setup/teardown code that tests can request by declaring a matching parameter name. 
When pytest sees def test_foo(client, db), it looks up fixtures named client and db, runs them, injects their yielded values, 
and runs teardown after the test finishes. The yield is the dividing line: code before it is setup, code after it is teardown.

scope="session" on _create_tables controls how long the fixture lives:
"session" — runs once for the entire test run, shared across all tests
"function" (the default, what db and client use) — runs fresh for every single test
So the tables are created once before any test runs and dropped once at the very end. The db fixture, by contrast, opens a new transaction for every test and rolls it back afterward — that's how tests stay isolated without recreating tables.

autouse=True means the fixture activates automatically for every test in scope, without any test having to declare it as a parameter.

_create_tables has both scope="session" and autouse=True — it runs once, invisibly, for the whole suite
_mock_market_data has autouse=True with default function scope — it patches get_price / get_prices for every single test automatically, so no test accidentally hits real yfinance during the test run
'''
@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture
def db():
    # Each test runs inside a transaction that is rolled back on teardown,
    # keeping tests isolated without recreating tables.
    conn = _engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


@pytest.fixture(autouse=True)
def _mock_market_data():
    def _prices(tickers: list[str]) -> dict[str, float | None]:
        return {t: 200.0 for t in tickers}

    def _earnings_dates(tickers: list[str]) -> dict[str, None]:
        return {t: None for t in tickers}

    with patch("app.services.market_data.get_price", return_value=200.0), \
         patch("app.services.market_data.get_prices", side_effect=_prices), \
         patch("app.services.market_data.get_earnings_date", return_value=None), \
         patch("app.services.market_data.get_earnings_dates", side_effect=_earnings_dates):
        yield


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
