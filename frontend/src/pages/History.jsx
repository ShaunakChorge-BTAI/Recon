import { useEffect, useState } from "react";
import axios from "axios";

const BASE = "http://localhost:8000";

function StatusBadge({ status }) {
  const map = { completed: "badge-green", running: "badge-blue", failed: "badge-red" };
  return <span className={`badge ${map[status] || "badge-gray"}`}>{status}</span>;
}

export default function History({ navigate }) {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    fetchRuns();
  }, []);

  const fetchRuns = async () => {
    try {
      const res = await axios.get(`${BASE}/runs`);
      setRuns(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const filtered = filter === "all" ? runs : runs.filter((r) => r.status === filter);

  return (
    <div>
      <div className="section-title">
        🕐 All Reconciliation Runs
      </div>

      {/* Filter tabs */}
      <div className="tabs">
        {["all", "completed", "running", "failed"].map((f) => (
          <div
            key={f}
            className={`tab${filter === f ? " active" : ""}`}
            onClick={() => setFilter(f)}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
            {f === "all" && <span style={{ marginLeft: 6, color: "var(--text3)", fontSize: 11 }}>({runs.length})</span>}
          </div>
        ))}
      </div>

      <div className="card">
        {loading ? (
          <div className="empty-state" style={{ padding: "40px 20px" }}>
            <div className="empty-state-icon">⟳</div>
            <div className="empty-state-text">Loading runs...</div>
          </div>
        ) : filtered.length === 0 ? (
          <div className="empty-state" style={{ padding: "40px 20px" }}>
            <div className="empty-state-icon">📂</div>
            <div className="empty-state-text">No runs found</div>
            <div className="empty-state-sub">
              {filter === "all" ? 'Click "New Run" to start' : `No ${filter} runs`}
            </div>
          </div>
        ) : (
          <div className="tbl-wrap">
            <table>
              <thead>
                <tr>
                  <th>Run ID</th>
                  <th>Source File</th>
                  <th>Dest File</th>
                  <th>Status</th>
                  <th>Source Rows</th>
                  <th>Dest Rows</th>
                  <th>Matched</th>
                  <th>Unmatched</th>
                  <th>L0</th>
                  <th>L1</th>
                  <th>L2</th>
                  <th>L3</th>
                  <th>L4</th>
                  <th>Duration</th>
                  <th>Started</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((run) => (
                  <tr key={run.id}>
                    <td style={{ color: "var(--primary)", fontWeight: 700 }}>#{run.id}</td>
                    <td style={{ maxWidth: 140, overflow: "hidden", textOverflow: "ellipsis" }}>
                      {run.source_filename || "—"}
                    </td>
                    <td style={{ maxWidth: 140, overflow: "hidden", textOverflow: "ellipsis" }}>
                      {run.dest_filename || "—"}
                    </td>
                    <td><StatusBadge status={run.status} /></td>
                    <td>{(run.total_source || 0).toLocaleString()}</td>
                    <td>{(run.total_dest || 0).toLocaleString()}</td>
                    <td style={{ color: "var(--green)", fontWeight: 600 }}>
                      {(run.total_matched || 0).toLocaleString()}
                    </td>
                    <td style={{ color: "var(--amber)" }}>
                      {(run.total_unmatched || 0).toLocaleString()}
                    </td>
                    <td>{run.layer0_count || 0}</td>
                    <td>{run.layer1_count || 0}</td>
                    <td>{run.layer2_count || 0}</td>
                    <td>{run.layer3_count || 0}</td>
                    <td>{run.layer4_count || 0}</td>
                    <td style={{ color: "var(--text3)" }}>
                      {run.total_duration_sec ? `${run.total_duration_sec}s` : "—"}
                    </td>
                    <td style={{ color: "var(--text3)" }}>
                      {run.created_at ? new Date(run.created_at).toLocaleString() : "—"}
                    </td>
                    <td>
                      <button
                        className="btn btn-outline btn-sm"
                        onClick={() => navigate("run-detail", { runId: run.id })}
                      >
                        View
                      </button>
                      <button
                        className="btn btn-outline btn-sm"
                        style={{ marginLeft: 6, borderColor: "var(--primary)", color: "var(--primary)" }}
                        onClick={() => {
                          if (!run.mapping_json) {
                            alert("No mapping found for this run.");
                            return;
                          }
                          navigate("new-run", { mapping_json: run.mapping_json });
                        }}
                      >
                        Rerun
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}