import { useState } from "react";
import axios from "axios";

const BASE = "http://localhost:8000";

const DATE_FORMATS = [
  { label: "DD/MM/YYYY", value: "%d/%m/%Y" },
  { label: "MM/DD/YYYY", value: "%m/%d/%Y" },
  { label: "YYYY-MM-DD", value: "%Y-%m-%d" },
  { label: "Auto Detect", value: "" },
];

const LAYER_INFO = [
  { name: "Self Knock", color: "var(--cyan)" },
  { name: "Exact Match", color: "var(--green)" },
  { name: "Tolerance Match", color: "var(--primary)" },
  { name: "Subset Match", color: "var(--amber)" },
  { name: "Fuzzy Match", color: "var(--purple)" },
  { name: "LLM Match", color: "var(--pink)" },
];

export default function TestRun() {
  const [srcFile, setSrcFile] = useState(null);
  const [destFile, setDestFile] = useState(null);
  const [uploadData, setUploadData] = useState(null);
  const [mapping, setMapping] = useState({
    source: { datetime: "", amount: "", references: [] },
    dest: { datetime: "", amount: "", references: [] },
    date_mode: "datetime",
    date_format: "",
  });
  const [tolAmount, setTolAmount] = useState(10);
  const [tolTime, setTolTime] = useState(10);
  const [tolUnit, setTolUnit] = useState("minutes");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState("");

  const ACCEPT = ".xlsx,.xls,.csv,.txt,.pdf,.xml,.lin";

  const handleUpload = async () => {
    if (!srcFile || !destFile) {
      setError("Select both files first.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append("source", srcFile);
      fd.append("dest", destFile);
      const res = await axios.post(`${BASE}/upload`, fd);
      if (res.data.error) throw new Error(res.data.error);
      setUploadData(res.data);
    } catch (e) {
      setError(e.response?.data?.error || e.message || "Upload failed");
    } finally {
      setLoading(false);
    }
  };

  const toggleRef = (side, col) => {
    setMapping((prev) => {
      const refs = prev[side].references.includes(col)
        ? prev[side].references.filter((r) => r !== col)
        : [...prev[side].references, col];
      return { ...prev, [side]: { ...prev[side], references: refs } };
    });
  };

  const handleChange = (side, field, val) => {
    setMapping((prev) => ({ ...prev, [side]: { ...prev[side], [field]: val } }));
  };

  const handleRun = async () => {
    setError("");
    setResults(null);

    if (!srcFile || !destFile) { setError("Select files first."); return; }
    if (!mapping.source.datetime || !mapping.dest.datetime) { setError("Select DateTime columns."); return; }
    if (!mapping.source.amount || !mapping.dest.amount) { setError("Select Amount columns."); return; }
    if (!mapping.source.references.length || !mapping.dest.references.length) { setError("Select at least one Reference."); return; }

    setLoading(true);
    try {
      const timeInMinutes = tolUnit === "days" ? tolTime * 24 * 60 : Number(tolTime);
      const fd = new FormData();
      fd.append("source", srcFile);
      fd.append("dest", destFile);
      fd.append("mapping", JSON.stringify(mapping));
      fd.append("tol_amount", tolAmount);
      fd.append("tol_time", timeInMinutes);

      const res = await axios.post(`${BASE}/test-reconcile`, fd);
      setResults(res.data);
    } catch (e) {
      setError(e.response?.data?.error || e.message || "Test failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="section-title">⚡ Test Reconciliation — No Database Write</div>
      <div className="alert alert-amber" style={{ marginBottom: 20 }}>
        ⚠️ Test mode: Files are processed in memory only. No data is saved to the database.
      </div>

      {/* File Upload */}
      <div className="card">
        <div className="card-header"><span className="card-title">📂 Select Files</span></div>
        <div className="card-body">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
            <div>
              <div className="form-label">Source File</div>
              <div className={`upload-zone${srcFile ? " has-file" : ""}`} onClick={() => document.getElementById("t-src").click()}>
                <input id="t-src" type="file" accept={ACCEPT} style={{ display: "none" }} onChange={(e) => { setSrcFile(e.target.files[0]); setUploadData(null); }} />
                <div className="upload-zone-icon">{srcFile ? "✓" : "📄"}</div>
                <div className="upload-zone-text">{srcFile ? srcFile.name : "Click to select source file"}</div>
              </div>
            </div>
            <div>
              <div className="form-label">Destination File</div>
              <div className={`upload-zone${destFile ? " has-file" : ""}`} onClick={() => document.getElementById("t-dest").click()}>
                <input id="t-dest" type="file" accept={ACCEPT} style={{ display: "none" }} onChange={(e) => { setDestFile(e.target.files[0]); setUploadData(null); }} />
                <div className="upload-zone-icon">{destFile ? "✓" : "📄"}</div>
                <div className="upload-zone-text">{destFile ? destFile.name : "Click to select destination file"}</div>
              </div>
            </div>
          </div>
          {srcFile && destFile && !uploadData && (
            <button className="btn btn-outline" onClick={handleUpload} disabled={loading}>
              {loading ? "⟳ Reading..." : "Read Columns"}
            </button>
          )}
        </div>
      </div>

      {/* Column Mapping */}
      {uploadData && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
          {[
            { side: "source", cols: uploadData.source_columns, label: "Source Mapping" },
            { side: "dest", cols: uploadData.dest_columns, label: "Destination Mapping" },
          ].map(({ side, cols, label }) => (
            <div className="card" key={side}>
              <div className="card-header">
                <span className="card-title">{label}</span>
              </div>
              <div className="card-body">
                <div className="form-group">
                  <label className="form-label">DateTime</label>
                  <select className="form-select" value={mapping[side].datetime} onChange={(e) => handleChange(side, "datetime", e.target.value)}>
                    <option value="">— Select —</option>
                    {cols.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Amount</label>
                  <select className="form-select" value={mapping[side].amount} onChange={(e) => handleChange(side, "amount", e.target.value)}>
                    <option value="">— Select —</option>
                    {cols.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">References</label>
                  <div className="checkbox-group">
                    {cols.map((c) => (
                      <label key={c} className="checkbox-item">
                        <input type="checkbox" checked={mapping[side].references.includes(c)} onChange={() => toggleRef(side, c)} />
                        {c}
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Settings */}
      {uploadData && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header"><span className="card-title">⚙️ Settings</span></div>
          <div className="card-body" style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
            <div className="form-group">
              <label className="form-label">Date Mode</label>
              <div style={{ display: "flex", gap: 6 }}>
                {["date", "datetime"].map((m) => (
                  <button key={m} className={`btn btn-sm ${mapping.date_mode === m ? "btn-blue" : "btn-outline"}`} onClick={() => setMapping(p => ({ ...p, date_mode: m }))}>
                    {m}
                  </button>
                ))}
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Date Format</label>
              <select className="form-select" value={mapping.date_format} onChange={(e) => setMapping(p => ({ ...p, date_format: e.target.value }))}>
                {DATE_FORMATS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Amount Tolerance</label>
              <input className="form-input" type="number" min={0} value={tolAmount} onChange={(e) => setTolAmount(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Time Tolerance</label>
              <div style={{ display: "flex", gap: 6 }}>
                <input className="form-input" type="number" min={0} value={tolTime} onChange={(e) => setTolTime(e.target.value)} style={{ flex: 1 }} />
                <select className="form-select" style={{ width: 90 }} value={tolUnit} onChange={(e) => setTolUnit(e.target.value)}>
                  <option value="minutes">Min</option>
                  <option value="days">Days</option>
                </select>
              </div>
            </div>
          </div>
        </div>
      )}

      {error && <div className="alert alert-red" style={{ marginBottom: 12 }}>{error}</div>}

      {uploadData && (
        <button className="btn btn-blue" onClick={handleRun} disabled={loading} style={{ fontSize: 14 }}>
          {loading ? "⟳ Running test..." : "⚡ Run Test Reconciliation"}
        </button>
      )}

      {/* Results */}
      {results && (
        <div style={{ marginTop: 24 }}>
          <div className="section-title">Test Results</div>
          <div className="kpi-grid">
            <div className="kpi-card">
              <div className="kpi-label">Source Rows</div>
              <div className="kpi-value" style={{ color: "var(--cyan)", fontSize: 22 }}>{results.total_source}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Dest Rows</div>
              <div className="kpi-value" style={{ color: "var(--purple)", fontSize: 22 }}>{results.total_dest}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Total Matched</div>
              <div className="kpi-value" style={{ color: "var(--green)", fontSize: 22 }}>{results.total_matched}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Src Unmatched</div>
              <div className="kpi-value" style={{ color: "var(--amber)", fontSize: 22 }}>{results.total_unmatched_src}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Dest Unmatched</div>
              <div className="kpi-value" style={{ color: "var(--amber)", fontSize: 22 }}>{results.total_unmatched_dest}</div>
            </div>
          </div>

          <div className="layer-cards">
            {LAYER_INFO.map((l) => {
              const d = results.layers?.[l.name];
              return (
                <div key={l.name} className={`layer-card${d && d.count > 0 ? " done" : ""}`}>
                  <div className="layer-card-name">{l.name}</div>
                  <div className="layer-card-count" style={{ color: d?.count > 0 ? l.color : "var(--text3)" }}>
                    {d ? d.count : "—"}
                  </div>
                  {d?.time_sec != null && <div className="layer-card-time">⏱ {d.time_sec}s</div>}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
