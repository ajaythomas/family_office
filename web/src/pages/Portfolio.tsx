import { useEffect, useState } from "react";
import type { components } from "../types/api";
import { getPortfolio, addHolding, deleteHolding, sellHolding } from "../lib/api";

type HoldingRead = components["schemas"]["HoldingRead"];
type PortfolioRead = components["schemas"]["PortfolioRead"];

type Dialog =
  | { type: "closed" }
  | { type: "lots"; ticker: string }
  | { type: "ask"; holding: HoldingRead }
  | { type: "sell"; holding: HoldingRead; saleDate: string; salePrice: string; sellAll: boolean; sharesSold: string };

type AggregatedHolding = {
  ticker: string;
  totalShares: number;
  avgPurchasePrice: number;
  lotCount: number;
};

interface Props {
  portfolioId: string;
  token: string;
}

export default function Portfolio({ portfolioId, token }: Props) {
  const [portfolio, setPortfolio] = useState<PortfolioRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialog, setDialog] = useState<Dialog>({ type: "closed" });
  const [submitting, setSubmitting] = useState(false);

  const [ticker, setTicker] = useState("");
  const [shares, setShares] = useState("");
  const [purchasePrice, setPurchasePrice] = useState("");
  const [purchaseDate, setPurchaseDate] = useState("");
  const [addError, setAddError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getPortfolio(token, portfolioId)
      .then(setPortfolio)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [token, portfolioId]);

  const activeHoldings = portfolio?.holdings.filter((h) => !h.sale_date) ?? [];

  const aggregatedHoldings: AggregatedHolding[] = Object.values(
    activeHoldings.reduce<Record<string, HoldingRead[]>>((acc, h) => {
      (acc[h.ticker] ??= []).push(h);
      return acc;
    }, {}),
  ).map((lots) => {
    const totalShares = lots.reduce((s, l) => s + l.shares, 0);
    return {
      ticker: lots[0].ticker,
      totalShares,
      avgPurchasePrice: lots.reduce((s, l) => s + l.shares * l.purchase_price, 0) / totalShares,
      lotCount: lots.length,
    };
  });

  async function handleAddHolding(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setAddError(null);
    setSubmitting(true);
    try {
      const holding = await addHolding(token, portfolioId, {
        ticker: ticker.toUpperCase(),
        shares: parseFloat(shares),
        purchase_price: parseFloat(purchasePrice),
        purchase_date: purchaseDate,
      });
      setPortfolio((p) => (p ? { ...p, holdings: [...p.holdings, holding] } : p));
      setTicker("");
      setShares("");
      setPurchasePrice("");
      setPurchaseDate("");
    } catch (e: unknown) {
      setAddError(e instanceof Error ? e.message : "Failed to add holding");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(holding: HoldingRead) {
    setSubmitting(true);
    try {
      await deleteHolding(token, portfolioId, holding.id);
      setPortfolio((p) =>
        p ? { ...p, holdings: p.holdings.filter((h) => h.id !== holding.id) } : p,
      );
      setDialog({ type: "closed" });
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Failed to delete holding");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSell(holding: HoldingRead, saleDate: string, salePrice: string, sellAll: boolean, sharesSold: string) {
    setSubmitting(true);
    try {
      await sellHolding(token, portfolioId, holding.id, {
        sale_date: saleDate,
        sale_price: parseFloat(salePrice),
        shares_sold: sellAll ? undefined : parseFloat(sharesSold),
      });
      const refreshed = await getPortfolio(token, portfolioId);
      setPortfolio(refreshed);
      setDialog({ type: "closed" });
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Failed to record sale");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <p>Loading portfolio…</p>;
  if (error) return <p style={{ color: "red" }}>Error: {error}</p>;
  if (!portfolio) return null;

  return (
    <div>
      <h2 style={{ margin: "0 0 1rem" }}>{portfolio.name}</h2>

      {aggregatedHoldings.length === 0 ? (
        <p style={{ color: "#888" }}>No active holdings. Add one below.</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: "1.5rem" }}>
          <thead>
            <tr style={{ borderBottom: "2px solid #ddd", textAlign: "left" }}>
              <th style={th}>Ticker</th>
              <th style={th}>Total Shares</th>
              <th style={th}>Avg Price</th>
              <th style={th}></th>
            </tr>
          </thead>
          <tbody>
            {aggregatedHoldings.map((agg) => (
              <tr key={agg.ticker} style={{ borderBottom: "1px solid #eee" }}>
                <td style={{ ...td, fontWeight: "bold" }}>{agg.ticker}</td>
                <td style={td}>{agg.totalShares}</td>
                <td style={td}>${agg.avgPurchasePrice.toFixed(2)}</td>
                <td style={td}>
                  <button onClick={() => setDialog({ type: "lots", ticker: agg.ticker })}>
                    Manage ({agg.lotCount})
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h3 style={{ margin: "0 0 0.75rem" }}>Add Holding</h3>
      <form
        onSubmit={handleAddHolding}
        style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", alignItems: "flex-end" }}
      >
        <label style={fieldLabel}>
          Ticker
          <input
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="AAPL"
            required
            style={{ ...input, width: "80px" }}
          />
        </label>
        <label style={fieldLabel}>
          Shares
          <input
            type="number"
            value={shares}
            onChange={(e) => setShares(e.target.value)}
            placeholder="10"
            min="0.001"
            step="any"
            required
            style={{ ...input, width: "80px" }}
          />
        </label>
        <label style={fieldLabel}>
          Purchase Price
          <input
            type="number"
            value={purchasePrice}
            onChange={(e) => setPurchasePrice(e.target.value)}
            placeholder="150.00"
            min="0.01"
            step="any"
            required
            style={{ ...input, width: "110px" }}
          />
        </label>
        <label style={fieldLabel}>
          Purchase Date
          <input
            type="date"
            value={purchaseDate}
            onChange={(e) => setPurchaseDate(e.target.value)}
            min="1930-01-01"
            max={new Date().toISOString().split("T")[0]}
            required
            style={input}
          />
        </label>
        <button type="submit" disabled={submitting} style={{ padding: "0.4rem 1rem" }}>
          {submitting ? "Adding…" : "Add"}
        </button>
      </form>
      {addError && <p style={{ color: "red", marginTop: "0.5rem" }}>{addError}</p>}

      {dialog.type !== "closed" && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.4)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 100,
          }}
          onClick={() => setDialog({ type: "closed" })}
        >
          <div
            style={{
              background: "#fff",
              borderRadius: "8px",
              padding: "1.5rem",
              minWidth: "320px",
              boxShadow: "0 4px 20px rgba(0,0,0,0.2)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {dialog.type === "lots" && (() => {
              const lots = activeHoldings.filter((h) => h.ticker === dialog.ticker);
              return (
                <>
                  <h3 style={{ margin: "0 0 1rem" }}>{dialog.ticker} — {lots.length} lot{lots.length !== 1 ? "s" : ""}</h3>
                  <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: "1rem" }}>
                    <thead>
                      <tr style={{ borderBottom: "2px solid #ddd", textAlign: "left" }}>
                        <th style={th}>Shares</th>
                        <th style={th}>Purchase Price</th>
                        <th style={th}>Purchase Date</th>
                        <th style={th}></th>
                      </tr>
                    </thead>
                    <tbody>
                      {lots.map((lot) => (
                        <tr key={lot.id} style={{ borderBottom: "1px solid #eee" }}>
                          <td style={td}>{lot.shares}</td>
                          <td style={td}>${lot.purchase_price.toFixed(2)}</td>
                          <td style={td}>{lot.purchase_date}</td>
                          <td style={td}>
                            <button onClick={() => setDialog({ type: "ask", holding: lot })}>
                              Sell / Delete
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <button onClick={() => setDialog({ type: "closed" })}>Close</button>
                </>
              );
            })()}

            {dialog.type === "ask" && (
              <>
                <h3 style={{ margin: "0 0 1rem" }}>
                  {dialog.holding.ticker} — what would you like to do?
                </h3>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                  <button
                    onClick={() =>
                      setDialog({
                        type: "sell",
                        holding: dialog.holding,
                        saleDate: "",
                        salePrice: "",
                        sellAll: true,
                        sharesSold: "",
                      })
                    }
                  >
                    Mark as Sold
                  </button>
                  <button
                    onClick={() => handleDelete(dialog.holding)}
                    disabled={submitting}
                    style={{ color: "red" }}
                  >
                    {submitting ? "Deleting…" : "Delete (added by mistake)"}
                  </button>
                  <button onClick={() => setDialog({ type: "closed" })}>Cancel</button>
                </div>
              </>
            )}

            {dialog.type === "sell" && (
              <>
                <h3 style={{ margin: "0 0 1rem" }}>Sell {dialog.holding.ticker}</h3>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  <label style={fieldLabel}>
                    Sale Price
                    <input
                      type="number"
                      value={dialog.salePrice}
                      onChange={(e) => setDialog({ ...dialog, salePrice: e.target.value })}
                      placeholder="200.00"
                      min="0.01"
                      step="any"
                      style={input}
                    />
                  </label>
                  <label style={fieldLabel}>
                    Sale Date
                    <input
                      type="date"
                      value={dialog.saleDate}
                      onChange={(e) => setDialog({ ...dialog, saleDate: e.target.value })}
                      style={input}
                    />
                  </label>
                  <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={dialog.sellAll}
                      onChange={(e) => setDialog({ ...dialog, sellAll: e.target.checked, sharesSold: "" })}
                    />
                    All units ({dialog.holding.shares} shares)
                  </label>
                  {!dialog.sellAll && (
                    <label style={fieldLabel}>
                      Shares to Sell
                      <input
                        type="number"
                        value={dialog.sharesSold}
                        onChange={(e) => setDialog({ ...dialog, sharesSold: e.target.value })}
                        placeholder={String(dialog.holding.shares)}
                        min="0.0001"
                        max={dialog.holding.shares}
                        step="any"
                        style={{ ...input, width: "110px" }}
                      />
                    </label>
                  )}
                  <button
                    onClick={() => handleSell(dialog.holding, dialog.saleDate, dialog.salePrice, dialog.sellAll, dialog.sharesSold)}
                    disabled={submitting || !dialog.saleDate || !dialog.salePrice || (!dialog.sellAll && !dialog.sharesSold)}
                  >
                    {submitting ? "Saving…" : "Confirm Sale"}
                  </button>
                  <button onClick={() => setDialog({ type: "closed" })}>Cancel</button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

const th: React.CSSProperties = { padding: "0.5rem 0.75rem" };
const td: React.CSSProperties = { padding: "0.5rem 0.75rem" };
const input: React.CSSProperties = { padding: "0.4rem", fontSize: "inherit" };
const fieldLabel: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.25rem",
  fontSize: "0.9rem",
};
