import { useState, useEffect, useRef } from "react";
import axios from "axios";

const BASE = "http://localhost:8000";

const LAYER_INFO = [
  { name: "Self Knock", color: "var(--cyan)" },
  { name: "Exact Match", color: "var(--green)" },
  { name: "Tolerance Match", color: "var(--primary)" },
  { name: "Subset Match", color: "var(--amber)" },
  { name: "Fuzzy Match", color: "var(--purple)" },
  { name: "LLM Match", color: "var(--pink)" },
];

const DATE_FORMATS = [
  { label: "DD/MM/YYYY", value: "%d/%m/%Y" },
  { label: "MM/DD/YYYY", value: "%m/%d/%Y" },
  { label: "YYYY-MM-DD", value: "%Y-%m-%d" },
  { label: "DD-MM-YYYY", value: "%d-%m-%Y" },
  { label: "Auto Detect", value: "" },
];

// Step 1: File Upload
function StepUpload({ onDone }) {
  const [srcFile, setSrcFile] = useState(null);
  const [destFile, setDestFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [uploadProgress, setUploadProgress] = useState(0);

  const ACCEPT = ".xlsx,.xls,.csv,.txt,.pdf,.xml,.lin";

  const handleUpload = async () => {
    if (!srcFile || !destFile) {
      setError("Please select both source and destination files.");
      return;
    }
    setError("");
    setLoading(true);
    setUploadProgress(0);
    try {
      const fd = new FormData();
      fd.append("source", srcFile);
      fd.append("dest", destFile);
      const res = await axios.post(`${BASE}/upload`, fd, {
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            setUploadProgress(percentCompleted);
          }
        }
      });
      if (res.data.error) throw new Error(res.data.error);
      onDone(res.data);
    } catch (e) {
      setError(e.response?.data?.error || e.message || "Upload failed");
    } finally {
      setLoading(false);
    }
  };

  const DropZone = ({ label, file, setFile, id }) => (
    <div
      className={`upload-zone${file ? " has-file" : ""}`}
      onClick={() => document.getElementById(id).click()}
    >
      <input
        id={id}
        type="file"
        accept={ACCEPT}
        style={{ display: "none" }}
        onChange={(e) => setFile(e.target.files[0])}
      />
      <div className="upload-zone-icon">{file ? "✓" : "📄"}</div>
      <div className="upload-zone-text">
        {file ? file.name : `Click to select ${label} file`}
      </div>
      <div className="upload-zone-sub">
        {file
          ? `${(file.size / 1024).toFixed(1)} KB`
          : "XLSX, XLS, CSV, TXT, PDF, XML, LIN"}
      </div>
    </div>
  );

  return (
    <div>
      <div className="section-title">Step 1 — Upload Files</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
        <div>
          <div className="form-label" style={{ marginBottom: 8 }}>Source File</div>
          <DropZone label="source" file={srcFile} setFile={setSrcFile} id="src-upload" />
        </div>
        <div>
          <div className="form-label" style={{ marginBottom: 8 }}>Destination File</div>
          <DropZone label="destination" file={destFile} setFile={setDestFile} id="dest-upload" />
        </div>
      </div>

      {error && <div className="alert alert-red" style={{ marginBottom: 12 }}>{error}</div>}

      {loading && uploadProgress > 0 && uploadProgress < 100 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 13, color: "var(--text2)" }}>
            <span>Uploading files...</span>
            <span>{uploadProgress}%</span>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${uploadProgress}%` }} />
          </div>
        </div>
      )}

      {loading && uploadProgress === 100 && (
        <div style={{ marginBottom: 16, fontSize: 13, color: "var(--text2)" }}>
          ⟳ Reading columns...
        </div>
      )}

      {srcFile && destFile && (
        <button className="btn btn-blue" onClick={handleUpload} disabled={loading}>
          {loading ? "⟳ Processing..." : "Done — Read Columns →"}
        </button>
      )}
    </div>
  );
}

// Step 2: Column Mapping
function StepMapping({ uploadData, onDone, initialMapping }) {
  const { source_columns: srcCols, dest_columns: destCols } = uploadData;

  const defaultMapping = {
    source: { datetime: "", amount: "", references: [] },
    dest: { datetime: "", amount: "", references: [] },
    date_mode: "datetime",
    date_format: "",
  };

  const [mapping, setMapping] = useState(initialMapping || defaultMapping);
  const [error, setError] = useState("");

  const handleSaveTemplate = () => {
    const name = prompt("Enter a name for this mapping template:");
    if (!name) return;
    const templates = JSON.parse(localStorage.getItem("reconTemplates") || "{}");
    templates[name] = mapping;
    localStorage.setItem("reconTemplates", JSON.stringify(templates));
    alert("Template saved!");
  };

  const handleLoadTemplate = () => {
    const templates = JSON.parse(localStorage.getItem("reconTemplates") || "{}");
    const names = Object.keys(templates);
    if (names.length === 0) {
      alert("No templates saved yet.");
      return;
    }
    const name = prompt(`Enter template name to load:\n${names.join(", ")}`);
    if (name && templates[name]) {
      setMapping(templates[name]);
    } else if (name) {
      alert("Template not found.");
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

  const handleGlobal = (field, val) => {
    setMapping((prev) => ({ ...prev, [field]: val }));
  };

  const validate = () => {
    const { source, dest } = mapping;
    if (!source.datetime || !dest.datetime) return "Please select DateTime for both files.";
    if (!source.amount || !dest.amount) return "Please select Amount for both files.";
    if (!source.references.length || !dest.references.length) return "Please select at least one Reference for each file.";
    return "";
  };

  const handleNext = () => {
    const err = validate();
    if (err) { setError(err); return; }
    setError("");
    onDone(mapping);
  };

  return (
    <div>
      <div className="section-title" style={{ display: "flex", justifyContent: "space-between" }}>
        <span>Step 2 — Column Mapping</span>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-outline btn-sm" onClick={handleLoadTemplate}>
            📂 Load Template
          </button>
          <button className="btn btn-outline btn-sm" onClick={handleSaveTemplate}>
            💾 Save Template
          </button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
        {[
          { side: "source", cols: srcCols, label: "Source File" },
          { side: "dest", cols: destCols, label: "Destination File" },
        ].map(({ side, cols, label }) => (
          <div className="card" key={side}>
            <div className="card-header">
              <span style={{ fontSize: 14 }}>{side === "source" ? "📥" : "📤"}</span>
              <span className="card-title">{label}</span>
            </div>
            <div className="card-body">
              <div className="form-group">
                <label className="form-label">📅 DateTime Column</label>
                <select
                  className="form-select"
                  value={mapping[side].datetime}
                  onChange={(e) => handleChange(side, "datetime", e.target.value)}
                >
                  <option value="">— Select —</option>
                  {cols.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">💰 Amount Column</label>
                <select
                  className="form-select"
                  value={mapping[side].amount}
                  onChange={(e) => handleChange(side, "amount", e.target.value)}
                >
                  <option value="">— Select —</option>
                  {cols.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">🔗 Reference Columns (select all that apply)</label>
                <div className="checkbox-group">
                  {cols.map((c) => (
                    <label key={c} className="checkbox-item">
                      <input
                        type="checkbox"
                        checked={mapping[side].references.includes(c)}
                        onChange={() => toggleRef(side, c)}
                      />
                      {c}
                    </label>
                  ))}
                </div>
                {mapping[side].references.length > 0 && (
                  <div className="helper-text" style={{ marginTop: 6 }}>
                    Selected: {mapping[side].references.join(", ")}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Global settings */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">⚙️ Date Settings</span>
        </div>
        <div className="card-body" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <div className="form-group">
            <label className="form-label">Date Type</label>
            <div style={{ display: "flex", gap: 8 }}>
              {["date", "datetime"].map((m) => (
                <button
                  key={m}
                  className={`btn btn-sm ${mapping.date_mode === m ? "btn-blue" : "btn-outline"}`}
                  onClick={() => handleGlobal("date_mode", m)}
                >
                  {m === "date" ? "📅 Date" : "🕐 Datetime"}
                </button>
              ))}
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Date Format</label>
            <select
              className="form-select"
              value={mapping.date_format}
              onChange={(e) => handleGlobal("date_format", e.target.value)}
            >
              {DATE_FORMATS.map((f) => (
                <option key={f.value} value={f.value}>{f.label}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {error && <div className="alert alert-red" style={{ marginBottom: 12 }}>{error}</div>}

      <button className="btn btn-blue" onClick={handleNext}>
        Next — Set Tolerances →
      </button>
    </div>
  );
}

// Step 3: Tolerances
function StepTolerances({ mapping, onDone }) {
  const [tolAmount, setTolAmount] = useState(10);
  const [tolTime, setTolTime] = useState(10);
  const [tolUnit, setTolUnit] = useState("minutes");

  const handleRun = () => {
    const timeInMinutes = tolUnit === "days" ? tolTime * 24 * 60 : Number(tolTime);
    onDone({ tolAmount: Number(tolAmount), tolTime: timeInMinutes, mapping });
  };

  return (
    <div>
      <div className="section-title">Step 3 — Tolerance Settings</div>
      <div className="card">
        <div className="card-body">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
            <div className="form-group">
              <label className="form-label">💰 Amount Tolerance</label>
              <input
                className="form-input"
                type="number"
                min={0}
                value={tolAmount}
                onChange={(e) => setTolAmount(e.target.value)}
                placeholder="e.g. 10"
              />
              <div className="helper-text">Max allowed difference in amount between records</div>
            </div>

            <div className="form-group">
              <label className="form-label">⏱ Time Tolerance</label>
              <div style={{ display: "flex", gap: 8 }}>
                <input
                  className="form-input"
                  type="number"
                  min={0}
                  value={tolTime}
                  onChange={(e) => setTolTime(e.target.value)}
                  placeholder="e.g. 10"
                  style={{ flex: 1 }}
                />
                <div style={{ display: "flex", gap: 4 }}>
                  {["minutes", "days"].map((u) => (
                    <button
                      key={u}
                      className={`btn btn-sm ${tolUnit === u ? "btn-blue" : "btn-outline"}`}
                      onClick={() => setTolUnit(u)}
                    >
                      {u}
                    </button>
                  ))}
                </div>
              </div>
              <div className="helper-text">Max allowed time difference between records</div>
            </div>
          </div>
        </div>
      </div>

      <div className="alert alert-blue" style={{ marginBottom: 16 }}>
        ℹ️ Date mode: <strong>{mapping.date_mode}</strong> |
        Date format: <strong>{mapping.date_format || "Auto Detect"}</strong>
      </div>

      <button className="btn btn-green" onClick={handleRun} style={{ fontSize: 14 }}>
        ▶ Upload & Run Reconciliation
      </button>
    </div>
  );
}

// Step 4: Live Tracking
function StepTracking({ runId, onViewResults }) {
  const [progress, setProgress] = useState(0);
  const [statusMsg, setStatusMsg] = useState("Connecting...");
  const [layerData, setLayerData] = useState({});
  const [done, setDone] = useState(false);
  const wsRef = useRef(null);

  useEffect(() => {
    if (!runId) return;

    const ws = new WebSocket(`ws://localhost:8000/ws/progress/${runId}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setProgress(data.progress || 0);
      setStatusMsg(data.status || "");

      if (data.layer && data.count !== undefined) {
        setLayerData((prev) => ({
          ...prev,
          [data.layer]: { count: data.count, time: data.time_sec },
        }));
      }

      if (data.layer_counts) {
        const newLayers = {};
        Object.entries(data.layer_counts).forEach(([name, count]) => {
          newLayers[name] = { count, time: data.layer_times?.[name] };
        });
        setLayerData(newLayers);
      }

      if (data.progress === 100 || data.progress === -1) {
        setDone(true);
        ws.close();
      }
    };

    ws.onerror = () => setStatusMsg("WebSocket error");
    ws.onclose = () => { if (!done) setStatusMsg("Connection closed"); };

    return () => ws.close();
  }, [runId]);

  const isError = progress === -1;

  return (
    <div>
      <div className="section-title">Step 4 — Live Tracking</div>

      <div className="card">
        <div className="card-body">
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
            <span style={{ fontSize: 13, color: "var(--text2)" }}>{statusMsg}</span>
            <span style={{ fontSize: 13, fontWeight: 700, color: isError ? "var(--red)" : "var(--primary)" }}>
              {isError ? "Error" : `${Math.max(0, progress)}%`}
            </span>
          </div>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{
                width: `${Math.max(0, progress)}%`,
                background: isError ? "var(--red)" : undefined,
              }}
            />
          </div>
        </div>
      </div>

      {/* Layer cards */}
      {Object.keys(layerData).length > 0 && (
        <div>
          <div className="section-title" style={{ marginTop: 20 }}>Layer Results</div>
          <div className="layer-cards">
            {LAYER_INFO.map((l) => {
              const d = layerData[l.name];
              return (
                <div key={l.name} className={`layer-card${d ? " done" : ""}`}>
                  <div className="layer-card-name">{l.name}</div>
                  <div className="layer-card-count" style={{ color: d ? l.color : "var(--text3)" }}>
                    {d ? d.count.toLocaleString() : "—"}
                  </div>
                  {d?.time != null && (
                    <div className="layer-card-time">⏱ {d.time}s</div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {done && !isError && (
        <div style={{ marginTop: 20 }}>
          <div className="alert alert-green" style={{ marginBottom: 16 }}>
            ✓ Reconciliation completed successfully!
          </div>
          <button className="btn btn-blue" onClick={() => onViewResults(runId)}>
            View Results →
          </button>
        </div>
      )}

      {isError && (
        <div className="alert alert-red" style={{ marginTop: 16 }}>
          ❌ {statusMsg}
        </div>
      )}
    </div>
  );
}

export default function NewRun({ navigate, initialMapping }) {
  const [step, setStep] = useState(1);
  const [uploadData, setUploadData] = useState(null);
  const [mapping, setMapping] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [error, setError] = useState("");
  const [cleaningProgress, setCleaningProgress] = useState(-1);

  // Update mapping if initialMapping changes
  useEffect(() => {
    if (initialMapping && step <= 2) {
      setMapping(initialMapping);
    }
  }, [initialMapping, step]);

  const handleUploadDone = (data) => {
    setUploadData(data);
    setStep(2);
  };

  const handleMappingDone = (mappingData) => {
    setMapping(mappingData);
    setStep(3);
  };

  const handleRunStart = async ({ tolAmount, tolTime, mapping: mappingData }) => {
    setError("");
    setCleaningProgress(0);
    let interval;
    try {
      interval = setInterval(() => {
        setCleaningProgress((p) => (p < 90 ? p + Math.floor(Math.random() * 15) : p));
      }, 600);

      // 1. Ingest
      const ingestFd = new FormData();
      ingestFd.append("source_upload_id", uploadData.source_upload_id);
      ingestFd.append("dest_upload_id", uploadData.dest_upload_id);
      ingestFd.append("mapping", JSON.stringify(mappingData));
      await axios.post(`${BASE}/ingest-mapped`, ingestFd);

      clearInterval(interval);
      setCleaningProgress(100);

      // 2. Start reconciliation
      const reconFd = new FormData();
      reconFd.append("source_upload_id", uploadData.source_upload_id);
      reconFd.append("dest_upload_id", uploadData.dest_upload_id);
      reconFd.append("mapping", JSON.stringify(mappingData));
      reconFd.append("tol_amount", tolAmount);
      reconFd.append("tol_time", tolTime);
      const res = await axios.post(`${BASE}/reconcile_async`, reconFd);
      setJobId(res.data.job_id);
      setStep(4);
      setCleaningProgress(-1);
    } catch (e) {
      if (interval) clearInterval(interval);
      setCleaningProgress(-1);
      setError(e.response?.data?.error || e.message || "Failed to start reconciliation");
    }
  };

  const STEPS = ["Upload Files", "Map Columns", "Tolerances", "Live Tracking"];

  return (
    <div>
      {/* Step indicator */}
      <div className="steps" style={{ marginBottom: 28 }}>
        {STEPS.map((label, i) => (
          <div key={i} className="step" style={{ alignItems: "center" }}>
            <div className={`step-circle ${step > i + 1 ? "done" : step === i + 1 ? "active" : ""}`}>
              {step > i + 1 ? "✓" : i + 1}
            </div>
            <span className={`step-label ${step === i + 1 ? "active" : step > i + 1 ? "done" : ""}`}>
              {label}
            </span>
            {i < STEPS.length - 1 && (
              <div className="step-line" style={{ flex: 1, margin: "0 8px", height: 2, background: step > i + 1 ? "var(--green)" : "var(--border)" }} />
            )}
          </div>
        ))}
      </div>

      {error && <div className="alert alert-red" style={{ marginBottom: 16 }}>{error}</div>}

      {step === 1 && <StepUpload onDone={handleUploadDone} />}
      {step === 2 && uploadData && <StepMapping uploadData={uploadData} onDone={handleMappingDone} initialMapping={initialMapping} />}
      {step === 3 && mapping && (
        <StepTolerances mapping={mapping} onDone={handleRunStart} />
      )}

      {cleaningProgress >= 0 && (
        <div className="card" style={{ marginTop: 20 }}>
          <div className="card-body">
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 13, color: "var(--text2)" }}>
              <span>{cleaningProgress < 100 ? "Cleaning and ingesting data..." : "Done!"}</span>
              <span>{cleaningProgress}%</span>
            </div>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${cleaningProgress}%` }} />
            </div>
          </div>
        </div>
      )}

      {step === 4 && jobId && (
        <StepTracking
          runId={jobId}
          onViewResults={(id) => navigate("run-detail", { runId: Number(id) })}
        />
      )}
    </div>
  );
}
