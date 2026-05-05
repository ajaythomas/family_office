// Manager can do everything
permit(principal, action, resource)
when { principal.role == "manager" };

// Member can read and write their own portfolio
// action should be fully qualified - so action in ["readPortfolio", "writePortfolio"] didn't work
permit(
  principal,
  action in [FamilyOffice::Action::"readPortfolio", FamilyOffice::Action::"writePortfolio"],
  resource
)
when { resource.owner == principal.id };
