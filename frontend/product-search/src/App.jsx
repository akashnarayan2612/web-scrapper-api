import { useState, useEffect } from "react";

const API_BASE = "http://localhost:8000";

const NOON_COLOR = "#D4980A";
const EMAX_COLOR = "#C0281E";

const styles = `
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@400;500&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg: #F5F4F0;
    --surface: #FFFFFF;
    --border: #E0DDD6;
    --border-strong: #C8C4BC;
    --text: #1A1916;
    --muted: #888580;
    --noon: ${NOON_COLOR};
    --emax: ${EMAX_COLOR};
    --noon-dim: rgba(212,152,10,0.08);
    --emax-dim: rgba(192,40,30,0.08);
  }

  html, body, #root {
    height: 100%;
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Mono', monospace;
    font-size: 13px;
    -webkit-font-smoothing: antialiased;
  }

  .app {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  /* ── Header ── */
  .header {
    padding: 40px 40px 0;
    position: relative;
    margin: 0 0 0 0;
  }

  .header-eyebrow {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.2em;
    color: var(--muted);
    text-transform: uppercase;
    margin-bottom: 12px;
  }

  .header-title {
    font-family: 'Syne', sans-serif;
    font-size: clamp(28px, 4vw, 52px);
    font-weight: 800;
    line-height: 1;
    letter-spacing: -0.03em;
    color: var(--text);
    margin-bottom: 6px;
  }

  .header-title span.noon-accent { color: var(--noon); }
  .header-title span.emax-accent { color: var(--emax); }

  .header-sub {
    font-size: 12px;
    color: var(--muted);
    margin-bottom: 28px;
  }

  /* ── Search ── */
  .search-wrap {
    padding: 0 40px 32px;
    position: relative;
  }

  .search-inner {
    position: relative;
    max-width: 680px;
  }

  .search-icon {
    position: absolute;
    left: 18px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--muted);
    font-size: 16px;
    pointer-events: none;
  }

  .search-input {
    width: 100%;
    padding: 14px 18px 14px 48px;
    background: var(--surface);
    border: 1px solid var(--border-strong);
    border-radius: 6px;
    color: var(--text);
    font-family: 'DM Mono', monospace;
    font-size: 14px;
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  }

  .search-input::placeholder { color: var(--muted); }
  .search-input:focus { border-color: #999; box-shadow: 0 0 0 3px rgba(0,0,0,0.06); }

  .search-count {
    position: absolute;
    right: 16px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 11px;
    color: var(--muted);
    letter-spacing: 0.05em;
  }

  /* ── Stats bar ── */
  .stats-bar {
    padding: 0 40px 28px;
    display: flex;
    gap: 24px;
    align-items: center;
  }

  .stat-pill {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .stat-pill.noon { background: var(--noon-dim); border: 1px solid rgba(212,152,10,0.25); }
  .stat-pill.emax { background: var(--emax-dim); border: 1px solid rgba(192,40,30,0.25); }

  .stat-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
  }
  .stat-pill.noon .stat-dot { background: var(--noon); }
  .stat-pill.emax .stat-dot { background: var(--emax); }

  .stat-pill .count {
    font-weight: 500;
    margin-left: 2px;
  }
  .stat-pill.noon .count { color: var(--noon); }
  .stat-pill.emax .count { color: var(--emax); }

  /* ── Divider ── */
  .divider {
    height: 1px;
    background: var(--border);
    margin: 0 40px 28px;
  }

  /* ── Tables layout ── */
  .tables-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    flex: 1;
    margin: 0 40px 40px;
    overflow: hidden;
  }

  .table-panel {
    background: var(--surface);
    display: flex;
    flex-direction: column;
    min-height: 0;
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  }

  /* ── Panel header ── */
  .panel-header {
    padding: 14px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    background: var(--surface);
    z-index: 2;
  }

  .panel-label {
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: 'Syne', sans-serif;
    font-weight: 700;
    font-size: 15px;
    letter-spacing: -0.01em;
  }

  .panel-bar {
    width: 3px;
    height: 18px;
    border-radius: 2px;
  }

  .panel-noon .panel-bar { background: var(--noon); }
  .panel-emax .panel-bar { background: var(--emax); }
  .panel-noon .panel-label { color: var(--text); }
  .panel-emax .panel-label { color: var(--text); }

  .panel-meta {
    font-size: 11px;
    color: var(--muted);
    letter-spacing: 0.05em;
  }

  /* ── Table ── */
  .table-scroll {
    overflow-y: auto;
    flex: 1;
    max-height: 600px;
  }

  .table-scroll::-webkit-scrollbar { width: 4px; }
  .table-scroll::-webkit-scrollbar-track { background: transparent; }
  .table-scroll::-webkit-scrollbar-thumb { background: #CCC; border-radius: 2px; }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  thead {
    position: sticky;
    top: 0;
    z-index: 1;
    background: #FAFAF8;
  }

  th {
    padding: 10px 20px;
    text-align: left;
    font-size: 10px;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--muted);
    font-weight: 500;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
  }

  th.right, td.right { text-align: right; }

  tbody tr {
    border-bottom: 1px solid var(--border);
    transition: background 0.1s;
    cursor: pointer;
  }

  tbody tr:last-child { border-bottom: none; }
  tbody tr:hover { background: #F8F7F3; }

  td {
    padding: 12px 20px;
    font-size: 12px;
    color: var(--text);
    vertical-align: middle;
  }

  .product-img {
    width: 36px;
    height: 36px;
    object-fit: contain;
    border-radius: 2px;
    background: #F5F4F0;
    display: block;
    border: 1px solid var(--border);
  }

  .product-img-placeholder {
    width: 36px;
    height: 36px;
    background: #EFEFEB;
    border-radius: 2px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #BBB;
    font-size: 16px;
  }

  .product-name {
    max-width: 240px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--text);
    text-decoration: none;
    display: block;
  }

  .product-name:hover { color: #aaa; }

  .product-brand {
    font-size: 10px;
    color: var(--muted);
    margin-top: 2px;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  .price-current {
    font-family: 'Syne', sans-serif;
    font-weight: 600;
    font-size: 13px;
  }

  .panel-noon .price-current { color: var(--noon); }
  .panel-emax .price-current { color: var(--emax); }

  .price-original {
    font-size: 10px;
    color: var(--muted);
    text-decoration: line-through;
    margin-top: 2px;
  }

  .discount-badge {
    display: inline-block;
    padding: 2px 6px;
    border-radius: 2px;
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.04em;
  }

  .panel-noon .discount-badge { background: rgba(255,235,0,0.12); color: var(--noon); }
  .panel-emax .discount-badge { background: rgba(230,51,41,0.12); color: var(--emax); }

  .rating-wrap {
    display: flex;
    align-items: center;
    gap: 4px;
    color: var(--muted);
    font-size: 11px;
  }

  .rating-star { color: #f5a623; }

  /* ── States ── */
  .empty-state {
    padding: 60px 20px;
    text-align: center;
    color: var(--muted);
  }

  .empty-icon { font-size: 32px; margin-bottom: 12px; opacity: 0.4; }
  .empty-text { font-size: 12px; letter-spacing: 0.05em; }

  .loading-row td {
    padding: 60px 20px;
    text-align: center;
    color: var(--muted);
  }

  .spinner {
    display: inline-block;
    width: 16px; height: 16px;
    border: 2px solid #DDD;
    border-top-color: #999;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    margin-right: 8px;
    vertical-align: middle;
  }

  @keyframes spin { to { transform: rotate(360deg); } }

  .error-text { color: #e05; font-size: 11px; }

  /* ── Pagination ── */
  .pagination {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 14px 20px;
    border-top: 1px solid var(--border);
  }

  .page-btn {
    padding: 5px 12px;
    background: var(--surface);
    border: 1px solid var(--border-strong);
    border-radius: 4px;
    color: var(--muted);
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .page-btn:hover:not(:disabled) { border-color: #999; color: var(--text); background: #F0EFEb; }
  .page-btn:disabled { opacity: 0.35; cursor: default; }
  .page-btn.active { border-color: #999; color: var(--text); background: #EEECEA; }

  .page-info { font-size: 11px; color: var(--muted); }
`;

function useProducts(source, search, page) {
  const [data, setData] = useState([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchProducts() {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams({
          source,
          limit: 20,
          page,
          sort_by: "price",
          sort_order: "asc",
        });
        if (search) params.set("search", search);

        const res = await fetch(`${API_BASE}/products?${params}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (!cancelled) {
          setData(json.results || []);
          setTotal(json.total || 0);
          setPages(json.pages || 1);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e.message);
          setData([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchProducts();
    return () => {
      cancelled = true;
    };
  }, [source, search, page]);

  return { data, total, pages, loading, error };
}

function useStats() {
  const [stats, setStats] = useState({});
  useEffect(() => {
    fetch(`${API_BASE}/stats`)
      .then((r) => r.json())
      .then((d) => {
        const map = {};
        (d.by_source || []).forEach((s) => {
          map[s.source] = s;
        });
        setStats(map);
      })
      .catch(() => {});
  }, []);
  return stats;
}

// Wrapper uses `key=search` to remount inner table on search change — cleanly resets page
function ProductTable(props) {
  return <ProductTableInner key={props.search} {...props} />;
}

function ProductTableInner({
  source,
  search,
  accentColor,
  panelClass,
  label,
  logoText,
}) {
  const [page, setPage] = useState(1);
  const { data, total, pages, loading, error } = useProducts(
    source,
    search,
    page,
  );

  const discount = (price, original) => {
    if (!original || original <= price) return null;
    return Math.round((1 - price / original) * 100);
  };

  return (
    <div className={`table-panel ${panelClass}`}>
      <div className="panel-header">
        <div className="panel-label">
          <div className="panel-bar" />
          {logoText}
        </div>
        <div className="panel-meta">
          {loading ? "—" : `${total.toLocaleString()} products`}
        </div>
      </div>

      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th style={{ width: 48 }}></th>
              <th>Product</th>
              <th className="right">Price</th>
              <th className="right">Rating</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr className="loading-row">
                <td colSpan={4}>
                  <span className="spinner" />
                  searching...
                </td>
              </tr>
            )}
            {error && (
              <tr>
                <td
                  colSpan={4}
                  className="error-text"
                  style={{ padding: "20px" }}
                >
                  ⚠ Could not connect to API — is it running on port 8000?
                </td>
              </tr>
            )}
            {!loading && !error && data.length === 0 && (
              <tr>
                <td colSpan={4}>
                  <div className="empty-state">
                    <div className="empty-icon">◻</div>
                    <div className="empty-text">No products found</div>
                  </div>
                </td>
              </tr>
            )}
            {!loading &&
              data.map((p, i) => {
                const disc = discount(p.price, p.original_price);
                return (
                  <tr key={p._id || i}>
                    <td>
                      {p.image_url ? (
                        <img
                          className="product-img"
                          src={p.image_url}
                          alt=""
                          onError={(e) => {
                            e.target.style.display = "none";
                          }}
                        />
                      ) : (
                        <div className="product-img-placeholder">◻</div>
                      )}
                    </td>
                    <td>
                      {p.product_url ? (
                        <a
                          className="product-name"
                          href={p.product_url}
                          target="_blank"
                          rel="noreferrer"
                          title={p.name}
                        >
                          {p.name}
                        </a>
                      ) : (
                        <span className="product-name" title={p.name}>
                          {p.name}
                        </span>
                      )}
                      {p.brand && (
                        <div className="product-brand">{p.brand}</div>
                      )}
                    </td>
                    <td className="right">
                      <div className="price-current">
                        AED {p.price ? p.price.toLocaleString() : "—"}
                      </div>
                      {disc && (
                        <>
                          <div className="price-original">
                            AED {p.original_price.toLocaleString()}
                          </div>
                          <span className="discount-badge">{disc}% off</span>
                        </>
                      )}
                    </td>
                    <td className="right">
                      {p.rating > 0 ? (
                        <div
                          className="rating-wrap"
                          style={{ justifyContent: "flex-end" }}
                        >
                          <span className="rating-star">★</span>
                          {p.rating.toFixed(1)}
                        </div>
                      ) : (
                        <span style={{ color: "var(--muted)" }}>—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>

      {pages > 1 && (
        <div className="pagination">
          <button
            className="page-btn"
            onClick={() => setPage((p) => p - 1)}
            disabled={page === 1}
          >
            ← prev
          </button>
          <span className="page-info">
            pg {page} / {pages}
          </span>
          <button
            className="page-btn"
            onClick={() => setPage((p) => p + 1)}
            disabled={page === pages}
          >
            next →
          </button>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const stats = useStats();

  // Debounce search input
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 350);
    return () => clearTimeout(t);
  }, [search]);

  const noonStats = stats["noon"] || {};
  const emaxStats = stats["emax"] || {};

  return (
    <>
      <style>{styles}</style>
      <div className="app">
        <div className="header">
          <div className="header-eyebrow">UAE · Price Comparison</div>
          <div className="header-title">
            <span className="noon-accent">Noon</span>
            {" & "}
            <span className="emax-accent">Emax</span>
          </div>
          <div className="header-sub">
            Live product search across both platforms
          </div>
        </div>

        <div className="search-wrap">
          <div className="search-inner">
            <span className="search-icon">⌕</span>
            <input
              className="search-input"
              type="text"
              placeholder="Search products — e.g. Samsung, iPhone, laptop..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              autoFocus
            />
            {search && (
              <span className="search-count">
                searching for "{debouncedSearch}"
              </span>
            )}
          </div>
        </div>

        <div className="stats-bar">
          <div className="stat-pill noon">
            <div className="stat-dot" />
            Noon
            <span className="count">
              {noonStats.total_products?.toLocaleString() || "—"}
            </span>
            products
          </div>
          <div className="stat-pill emax">
            <div className="stat-dot" />
            Emax
            <span className="count">
              {emaxStats.total_products?.toLocaleString() || "—"}
            </span>
            products
          </div>
        </div>

        <div className="divider" />

        <div className="tables-row">
          <ProductTable
            source="noon"
            search={debouncedSearch}
            panelClass="panel-noon"
            label="Noon"
            logoText="NOON"
          />
          <ProductTable
            source="emax"
            search={debouncedSearch}
            panelClass="panel-emax"
            label="Emax"
            logoText="EMAX"
          />
        </div>
      </div>
    </>
  );
}
