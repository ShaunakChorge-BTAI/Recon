import { useState } from "react";
import Sidebar from "./layout/Sidebar";
import Topbar from "./layout/Topbar";
import Dashboard from "./pages/Dashboard";
import History from "./pages/History";
import RunDetail from "./pages/RunDetail";
import NewRun from "./pages/NewRun";
import TestRun from "./pages/TestRun";

export default function App() {
  const [page, setPage] = useState("dashboard");
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [mappingJson, setMappingJson] = useState(null);

  const navigate = (p, extras = {}) => {
    if (extras.runId !== undefined) setSelectedRunId(extras.runId);
    if (extras.mapping_json !== undefined) {
      setMappingJson(extras.mapping_json);
    } else if (p === "new-run") {
      setMappingJson(null); // Clear it if navigating normally
    }
    setPage(p);
  };

  const pageTitles = {
    dashboard: { title: "Dashboard", sub: "Overview & KPIs" },
    history: { title: "Run History", sub: "All reconciliation runs" },
    "run-detail": { title: `Run #${selectedRunId}`, sub: "Matched records & details" },
    "new-run": { title: "New Reconciliation", sub: "Upload files and run matching" },
    "test-run": { title: "Test Run", sub: "Test without saving to database" },
  };

  const currentMeta = pageTitles[page] || { title: "Recon 2.0", sub: "" };

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      <Sidebar currentPage={page} navigate={navigate} />

      <div className="main">
        <Topbar
          title={currentMeta.title}
          sub={currentMeta.sub}
          navigate={navigate}
          page={page}
        />

        <div className="page-content">
          {page === "dashboard" && <Dashboard navigate={navigate} />}
          {page === "history" && <History navigate={navigate} />}
          {page === "run-detail" && <RunDetail runId={selectedRunId} navigate={navigate} />}
          {page === "new-run" && <NewRun navigate={navigate} initialMapping={mappingJson} />}
          {page === "test-run" && <TestRun navigate={navigate} />}
        </div>
      </div>
    </div>
  );
}