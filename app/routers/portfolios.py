from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.cedar_authz import authorize
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Holding, Portfolio, User
from app.schemas import HoldingCreate, HoldingRead, HoldingSell, PortfolioRead

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


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
        return db.query(Portfolio).all()
    # Members only see their own portfolio
    if current_user.portfolio:
        return [current_user.portfolio]
    return []


@router.get("/{portfolio_id}", response_model=PortfolioRead)
def get_portfolio(
    portfolio_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Portfolio:
    portfolio = _get_portfolio_or_404(portfolio_id, db)
    authorize("readPortfolio", current_user, portfolio)
    return portfolio


@router.post("/{portfolio_id}/holdings", response_model=HoldingRead, status_code=201)
def add_holding(
    portfolio_id: str,
    body: HoldingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Holding:
    portfolio = _get_portfolio_or_404(portfolio_id, db)
    authorize("writePortfolio", current_user, portfolio)
    holding = Holding(portfolio_id=portfolio.id, **body.model_dump())
    db.add(holding)
    db.commit()
    db.refresh(holding)
    return holding


@router.delete("/{portfolio_id}/holdings/{holding_id}", status_code=204)
def remove_holding(
    portfolio_id: str,
    holding_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    portfolio = _get_portfolio_or_404(portfolio_id, db)
    authorize("writePortfolio", current_user, portfolio)
    holding = db.get(Holding, holding_id)
    if holding is None or holding.portfolio_id != portfolio_id:
        raise HTTPException(status_code=404, detail="Holding not found")
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
    authorize("writePortfolio", current_user, portfolio)
    holding = db.get(Holding, holding_id)
    if holding is None or holding.portfolio_id != portfolio_id:
        raise HTTPException(status_code=404, detail="Holding not found")
    holding.sale_price = body.sale_price
    holding.sale_date = body.sale_date
    db.commit()
    db.refresh(holding)
    return holding
