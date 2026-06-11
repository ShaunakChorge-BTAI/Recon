export default function Topbar({ title, sub, navigate, page }) {
  return (
    <div className="topbar">
      <div>
        <span className="topbar-title">{title}</span>
        {sub && <span className="topbar-sub">— {sub}</span>}
      </div>

      <div className="topbar-actions">
        {page !== "test-run" && (
          <button className="btn btn-outline btn-sm" onClick={() => navigate("test-run")}>
            ⚡ Run Test
          </button>
        )}
        {page !== "new-run" && (
          <button className="btn btn-blue btn-sm" onClick={() => navigate("new-run")}>
            ✦ New Run
          </button>
        )}
      </div>
    </div>
  );
}
