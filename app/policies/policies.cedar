// Manager can do everything
permit(principal, action, resource)
when { principal.role == "manager" };

// Member can read and write their own portfolio
permit(
  principal,
  action in [Action::"readPortfolio", Action::"writePortfolio"],
  resource
)
when { resource.owner == principal.id };
