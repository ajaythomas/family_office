import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.cedar_authz import authorize
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Portfolio, User
from app.services.google_calendar import create_earnings_event, get_valid_access_token

router = APIRouter(prefix="/portfolios", tags=["calendar"])
logger = logging.getLogger(__name__)


class EarningsCalendarResponse(BaseModel):
    events_created: int


def _sync_portfolio_calendar(portfolio: Portfolio, user: User, db: Session) -> int:
    if not user.google_calendar_token:
        return 0

    today = date.today()
    pending = [
        h for h in portfolio.holdings
        if not h.sale_date
        and not h.calendar_event_created
        and h.earnings_date is not None
        and h.earnings_date >= today
    ]
    if not pending:
        return 0

    access_token, updated_token = get_valid_access_token(user.google_calendar_token)
    if updated_token != user.google_calendar_token:
        user.google_calendar_token = updated_token

    created = 0
    for h in pending:
        assert h.earnings_date is not None
        try:
            create_earnings_event(access_token, h.ticker, h.earnings_date)
            h.calendar_event_created = True
            created += 1
            logger.info("Created calendar event for %s on %s", h.ticker, h.earnings_date)
        except Exception:
            logger.warning("Failed to create calendar event for %s", h.ticker)

    db.commit()
    return created


def run_calendar_cron() -> None:
    from app.database import SessionLocal
    from app.routers.portfolios import refresh_stale_earnings

    db = SessionLocal()
    try:
        users = db.query(User).filter(User.google_calendar_token.isnot(None)).all()
        for user in users:
            if user.portfolio:
                refresh_stale_earnings(user.portfolio, db)
                _sync_portfolio_calendar(user.portfolio, user, db)
    except Exception:
        logger.exception("Calendar cron failed")
    finally:
        db.close()


@router.post("/{portfolio_id}/earnings-calendar", response_model=EarningsCalendarResponse)
def sync_earnings_calendar(
    portfolio_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EarningsCalendarResponse:
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    authorize("readPortfolio", current_user, portfolio)

    if not current_user.google_calendar_token:
        raise HTTPException(status_code=400, detail="Google Calendar not connected")

    created = _sync_portfolio_calendar(portfolio, current_user, db)
    return EarningsCalendarResponse(events_created=created)
