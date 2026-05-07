import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.cedar_authz import authorize
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Holding, Portfolio, User
from app.schemas import HoldingCreate, HoldingRead, HoldingReadEnriched, HoldingSell, PortfolioRead, PortfolioReadEnriched
from app.services.market_data import get_price, get_prices

router = APIRouter(prefix="/portfolios", tags=["portfolios"])
logger = logging.getLogger(__name__)


def _get_portfolio_or_404(portfolio_id: str, db: Session) -> Portfolio:
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolio


@router.get("", response_model=list[PortfolioRead])
def list_portfolios(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Portfolio]:
    # An example where doing these checks with a Cedar policy would have made cedar schema complex
    # The authorize(action, user, portfolio) evaluates a Cedar (principal, action, resource) triple against one specific resource. 
    # list_portfolios doesn't have a single resource to check against; 
    # it's "which portfolios should this user see?" - a collection-scoping question, not a single-resource permit decision.

    # For a list endpoint to benefit from cedar authorize(), we will need to either:
    # 1. Post-filter: call authorize("readPortfolio", user, p) per portfolio in our entire db and drop the 403s — expensive duh
    # 2. Push the scoping logic into Cedar via a "list" action on a notional PortfolioCollection resource — works but adds schema complexity
    # So, went the route of inline Python checks
    if current_user.role.value == "manager":
        portfolios = db.query(Portfolio).all()
        logger.info("Manager %s listed all %d portfolios", current_user.email, len(portfolios))
        return portfolios
    # Members only see their own portfolio
    if current_user.portfolio:
        return [current_user.portfolio]
    return []


@router.get("/{portfolio_id}", response_model=PortfolioReadEnriched)
def get_portfolio(
    portfolio_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PortfolioReadEnriched:
    portfolio = _get_portfolio_or_404(portfolio_id, db)
    try:
        authorize("readPortfolio", current_user, portfolio)
    except HTTPException:
        logger.warning("User %s denied read access to portfolio %s", current_user.email, portfolio_id)
        raise

    active_tickers = [h.ticker for h in portfolio.holdings if not h.sale_date]
    prices = get_prices(active_tickers)

    enriched: list[HoldingReadEnriched] = []
    for h in portfolio.holdings:
        price = prices.get(h.ticker) if not h.sale_date else None
        current_value = h.shares * price if price is not None else None
        gain_loss = (current_value - (h.purchase_price * h.shares)) if current_value is not None else None
        enriched.append(HoldingReadEnriched(
            **HoldingRead.model_validate(h).model_dump(),
            current_price=price,
            current_value=current_value,
            gain_loss=gain_loss,
        ))

    return PortfolioReadEnriched(
        id=portfolio.id,
        owner_id=portfolio.owner_id,
        name=portfolio.name,
        holdings=enriched,
        created_at=portfolio.created_at,
    )


@router.post("/{portfolio_id}/holdings", response_model=HoldingRead, status_code=201)
def add_holding(
    portfolio_id: str,
    body: HoldingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Holding:
    portfolio = _get_portfolio_or_404(portfolio_id, db)
    try:
        authorize("writePortfolio", current_user, portfolio)
    except HTTPException:
        logger.warning("User %s denied write access to portfolio %s", current_user.email, portfolio_id)
        raise

    if get_price(body.ticker.upper()) is None:
        raise HTTPException(status_code=422, detail=f"Ticker '{body.ticker.upper()}' not found or price unavailable")

    holding = Holding(portfolio_id=portfolio.id, **body.model_dump())
    db.add(holding)
    db.commit()
    db.refresh(holding)
    logger.info("User %s added holding %s (%s shares) to portfolio %s", current_user.email, holding.ticker, holding.shares, portfolio_id)
    return holding


@router.delete("/{portfolio_id}/holdings/{holding_id}", status_code=204)
def remove_holding(
    portfolio_id: str,
    holding_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    portfolio = _get_portfolio_or_404(portfolio_id, db)
    try:
        authorize("writePortfolio", current_user, portfolio)
    except HTTPException:
        logger.warning("User %s denied write access to portfolio %s", current_user.email, portfolio_id)
        raise
    holding = db.get(Holding, holding_id)
    if holding is None or holding.portfolio_id != portfolio_id:
        raise HTTPException(status_code=404, detail="Holding not found")
    logger.info("User %s deleted holding %s from portfolio %s", current_user.email, holding.ticker, portfolio_id)
    db.delete(holding)
    db.commit()


@router.patch("/{portfolio_id}/holdings/{holding_id}/sell", response_model=HoldingRead)
def sell_holding(
    portfolio_id: str,
    holding_id: str,
    body: HoldingSell,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Holding:
    portfolio = _get_portfolio_or_404(portfolio_id, db)
    try:
        authorize("writePortfolio", current_user, portfolio)
    except HTTPException:
        logger.warning("User %s denied write access to portfolio %s", current_user.email, portfolio_id)
        raise
    holding = db.get(Holding, holding_id)
    if holding is None or holding.portfolio_id != portfolio_id:
        raise HTTPException(status_code=404, detail="Holding not found")

    if body.shares_sold is not None:
        if body.shares_sold <= 0 or body.shares_sold >= holding.shares:
            raise HTTPException(status_code=422, detail="shares_sold must be between 0 and the current share count (exclusive); omit to sell all")
        sold = Holding(
            portfolio_id=holding.portfolio_id,
            ticker=holding.ticker,
            shares=body.shares_sold,
            purchase_price=holding.purchase_price,
            purchase_date=holding.purchase_date,
            sale_price=body.sale_price,
            sale_date=body.sale_date,
        )
        holding.shares -= body.shares_sold
        db.add(sold)
        db.commit()
        db.refresh(holding)
        logger.info("User %s partially sold %s shares of %s at $%s on %s", current_user.email, body.shares_sold, holding.ticker, body.sale_price, body.sale_date)
    else:
        holding.sale_price = body.sale_price
        holding.sale_date = body.sale_date
        db.commit()
        db.refresh(holding)
        logger.info("User %s sold all of %s at $%s on %s", current_user.email, holding.ticker, body.sale_price, body.sale_date)
    return holding
