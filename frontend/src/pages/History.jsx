import { useEffect, useState } from "react";
import axios from "axios";

const BASE = "http://localhost:8000";

export default function History({ onSelectRun }) {

  const [runs, setRuns] = useState([]);

  useEffect(() => {
    fetchRuns();
  }, []);

  const fetchRuns = async () => {
    const res = await axios.get(`${BASE}/runs`);
    setRuns(res.data);
  };

  return (
    <div>

      <h2 className="text-xl font-bold text-blue-700 mb-4">
        Full History
      </h2>

      {runs.map(run => (
        <div
          key={run.id}
          className="bg-white p-3 rounded shadow mb-2 cursor-pointer"
          onClick={() => onSelectRun(run.id)}
        >
          Run {run.id} | {run.timestamp} | {run.duration}s
        </div>
      ))}

    </div>
  );
}