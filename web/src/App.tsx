import { useEffect, useState } from "react";
import type { components } from "./types/api";
import Login from "./pages/Login";
import Portfolio from "./pages/Portfolio";
import { getMe, listPortfolios } from "./lib/api";

type UserRead = components["schemas"]["UserRead"];
type PortfolioRead = components["schemas"]["PortfolioRead"];

export default function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem("token"));
  const [user, setUser] = useState<UserRead | null>(null);
  const [portfolios, setPortfolios] = useState<PortfolioRead[]>([]);
  const [loading, setLoading] = useState(!!token);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    Promise.all([getMe(token), listPortfolios(token)])
      .then(([u, ps]) => {
        setUser(u);
        setPortfolios(ps);
      })
      .catch(() => {
        localStorage.removeItem("token");
        setToken(null);
      })
      .finally(() => setLoading(false));
  }, [token]);

  function signOut() {
    localStorage.removeItem("token");
    setToken(null);
    setUser(null);
    setPortfolios([]);
  }

  if (!token) return <Login onLogin={setToken} />;
  if (loading) return <p style={{ padding: "2rem" }}>Loading…</p>;

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif", maxWidth: "960px", margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ margin: 0 }}>Family Office</h1>
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          {user && (
            <span style={{ color: "#555" }}>
              {user.name} · <span style={{ textTransform: "capitalize" }}>{user.role}</span>
            </span>
          )}
          <button onClick={signOut}>Sign out</button>
        </div>
      </div>
      <hr />
      {portfolios.length === 0 ? (
        <p style={{ color: "#888" }}>No portfolio found.</p>
      ) : (
        portfolios.map((p) => <Portfolio key={p.id} portfolioId={p.id} token={token} />)
      )}
    </div>
  );
}
