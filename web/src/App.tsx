import { useEffect, useState } from "react";
import type { components } from "./types/api";
import Login from "./pages/Login";
import { getMe } from "./lib/api";

type UserRead = components["schemas"]["UserRead"];

export default function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem("token"));
  const [user, setUser] = useState<UserRead | null>(null);
  const [loading, setLoading] = useState(!!token);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    getMe(token)
      .then(setUser)
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
  }

  if (!token) return <Login onLogin={setToken} />;
  if (loading) return <p style={{ padding: "2rem" }}>Loading…</p>;

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ margin: 0 }}>Family Office</h1>
        <button onClick={signOut}>Sign out</button>
      </div>
      <hr />
      {user && (
        <div>
          <p><strong>Name:</strong> {user.name}</p>
          <p><strong>Email:</strong> {user.email}</p>
          <p><strong>Role:</strong> <span style={{ textTransform: "capitalize" }}>{user.role}</span></p>
        </div>
      )}
    </div>
  );
}
