export default function Topbar({ title, sub, navigate, page, darkMode, toggleDark }) {
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
        {/* Dark / Light Mode Toggle */}
        <button
          id="dark-mode-toggle"
          className="btn btn-outline btn-sm"
          onClick={toggleDark}
          title={darkMode ? "Switch to Light Mode" : "Switch to Dark Mode"}
          style={{ fontSize: 16, padding: "4px 10px", minWidth: 36 }}
        >
          {darkMode ? "☀️" : "🌙"}
        </button>
      </div>
    </div>
  );
}
