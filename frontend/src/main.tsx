import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Database,
  GitCompare,
  Network,
  Play,
  RotateCcw,
  Search,
  ShieldAlert,
  XCircle
} from "lucide-react";
import { api, Diagnosis, Run, Step } from "./api/client";
import "./styles.css";

const scenarios = [
  ["valid/orders.csv", "Valid run"],
  ["failures/price_type_change.csv", "Price type change"],
  ["failures/missing_customer_id.csv", "Missing customer_id"],
  ["failures/duplicate_order_ids.csv", "Duplicate order_id"],
  ["failures/email_null_increase.csv", "Email null spike"],
  ["failures/row_count_decrease.csv", "Row-count drop"],
  ["failures/empty_orders.csv", "Empty input"]
];

function statusIcon(status: string) {
  if (status === "SUCCESS") return <CheckCircle2 className="ok" size={18} />;
  if (status === "FAILED") return <XCircle className="bad" size={18} />;
  return <Activity className="warn" size={18} />;
}

function statusClass(status: string) {
  return status.toLowerCase();
}

function StatusChip({ status }: { status: string }) {
  return <span className={`statusChip ${statusClass(status)}`}>{statusIcon(status)}{status}</span>;
}

function RunHistory({ runs, selected, onSelect, onRefresh }: { runs: Run[]; selected?: string; onSelect: (run: Run) => void; onRefresh: () => void }) {
  const [status, setStatus] = useState("");
  const [date, setDate] = useState("");
  const visible = runs.filter((run) => (!status || run.status === status) && (!date || run.started_at.startsWith(date)));
  return (
    <section className="panel history">
      <div className="toolbar">
        <div>
          <span className="eyebrow">Execution ledger</span>
          <h2>Run History</h2>
        </div>
        <button className="iconButton" title="Refresh" onClick={onRefresh}><RotateCcw size={18} /></button>
      </div>
      <div className="filters">
        <select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Status">
          <option value="">All statuses</option>
          <option value="SUCCESS">Success</option>
          <option value="FAILED">Failed</option>
          <option value="RUNNING">Running</option>
        </select>
        <input type="date" value={date} onChange={(event) => setDate(event.target.value)} />
      </div>
      <div className="tableWrap">
        <table>
          <thead>
            <tr>
              <th>Pipeline</th>
              <th>Run ID</th>
              <th>Status</th>
              <th>Start</th>
              <th>Duration</th>
              <th>Git</th>
              <th>Input</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((run) => (
              <tr key={run.run_id} className={selected === run.run_id ? "selected" : ""} onClick={() => onSelect(run)}>
                <td>{run.pipeline_id}</td>
                <td className="mono">{run.run_id.slice(0, 8)}</td>
                <td><StatusChip status={run.status} /></td>
                <td>{new Date(run.started_at).toLocaleString()}</td>
                <td>{run.duration_seconds?.toFixed(2) ?? "-"}</td>
                <td className="mono">{run.git_commit ?? "-"}</td>
                <td>{run.input_filename}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Runner({ onDone }: { onDone: (run: Run) => void }) {
  const [busy, setBusy] = useState("");
  async function trigger(file: string) {
    setBusy(file);
    try {
      onDone(await api.trigger(file));
    } finally {
      setBusy("");
    }
  }
  return (
    <section className="panel runner">
      <div>
        <span className="eyebrow">Scenario launcher</span>
        <h2>Manual Execution</h2>
      </div>
      <div className="scenarioGrid">
        {scenarios.map(([file, label], index) => (
          <button
            className={index === 0 ? "scenarioButton primary" : "scenarioButton"}
            key={file}
            onClick={() => trigger(file)}
            disabled={!!busy}
          >
            <Play size={16} /> {busy === file ? "Running" : label}
          </button>
        ))}
      </div>
    </section>
  );
}

function RunDetails({ run, steps, logs }: { run?: Run; steps: Step[]; logs: Array<{ level: string; message: string }> }) {
  if (!run) return <section className="panel empty"><Search size={32} />Select a run to inspect.</section>;
  return (
    <section className="panel details">
      <div className="headline">
        <StatusChip status={run.status} />
        <div>
          <span className="eyebrow">Selected run</span>
          <h2>{run.input_filename}</h2>
        </div>
      </div>
      {run.error_message && <div className="error"><AlertTriangle size={18} />{run.error_message}</div>}
      <div className="metaGrid">
        <label>Run ID<span className="mono">{run.run_id}</span></label>
        <label>Snapshot<span>{run.input_snapshot_path ?? "-"}</span></label>
        <label>Python<span>{String(run.environment_metadata?.python_version ?? "-")}</span></label>
        <label>Git Commit<span className="mono">{run.git_commit ?? "-"}</span></label>
      </div>
      <h3>Execution Timeline</h3>
      <div className="steps">
        {steps.map((step) => (
          <div className={`step ${step.status.toLowerCase()}`} key={step.step_id}>
            <span className="stepMarker">{statusIcon(step.status)}</span>
            <b>{step.step_name}</b>
            <small>{step.duration_seconds?.toFixed(2) ?? "-"}s</small>
            {step.error_message && <em>{step.error_message}</em>}
          </div>
        ))}
      </div>
      <h3>Logs</h3>
      <pre>{logs.map((log) => `[${log.level}] ${log.message}`).join("\n")}</pre>
    </section>
  );
}

function Investigation({ run, diagnoses, comparison, impact, onReplay }: { run?: Run; diagnoses: Diagnosis[]; comparison: any; impact: any; onReplay: () => void }) {
  if (!run) return null;
  const likely = diagnoses[0];
  return (
    <section className="panel investigation">
      <div className="toolbar">
        <div>
          <span className="eyebrow">Likely causes</span>
          <h2>Investigation</h2>
        </div>
        <button onClick={onReplay}><RotateCcw size={16} />Replay</button>
      </div>
      {likely && (
        <div className="likely">
          <span>Most likely cause</span>
          <strong>{likely.title}</strong>
          <p>{likely.description}</p>
        </div>
      )}
      <h3><ShieldAlert size={18} /> Ranked Diagnoses</h3>
      <div className="diagnoses">
        {diagnoses.map((item) => (
          <article key={item.title}>
            <b>{item.title}</b>
            <span>{item.confidence} confidence · {item.severity}</span>
            <p>{item.description}</p>
          </article>
        ))}
      </div>
      <h3><GitCompare size={18} /> Comparison</h3>
      <table>
        <thead><tr><th>Column or Metric</th><th>Successful run</th><th>Failed run</th><th>Difference</th></tr></thead>
        <tbody>
          {(comparison?.schema_changes ?? []).map((change: any) => (
            <tr key={`${change.column}${change.change_type}`}>
              <td>{change.column}</td><td>{change.previous_type ?? "Missing"}</td><td>{change.current_type ?? "Missing"}</td><td>{change.change_type}</td>
            </tr>
          ))}
          {(comparison?.profile_changes ?? []).filter((change: any) => ["row_count", "email_null_percentage", "order_id_duplicate_rate"].includes(change.metric)).map((change: any) => (
            <tr key={change.metric}>
              <td>{change.metric}</td><td>{String(change.previous_value)}</td><td>{String(change.current_value)}</td><td>{change.change_percentage ?? "-"}%</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h3><Network size={18} /> Dependency View</h3>
      <div className="graph">
        {(impact?.graph?.nodes ?? []).map((node: any) => <span key={node.node_id} className={node.state.toLowerCase()}>{node.name}</span>)}
      </div>
      <p className="impact">Affected downstream assets: {(impact?.affected_nodes ?? []).map((node: any) => node.name).join(", ") || "None"}</p>
    </section>
  );
}

function App() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [selected, setSelected] = useState<Run | undefined>();
  const [steps, setSteps] = useState<Step[]>([]);
  const [logs, setLogs] = useState<Array<{ level: string; message: string }>>([]);
  const [diagnoses, setDiagnoses] = useState<Diagnosis[]>([]);
  const [comparison, setComparison] = useState<any>();
  const [impact, setImpact] = useState<any>();
  const [notice, setNotice] = useState("");

  async function refresh(selectRunId?: string) {
    const next = await api.runs();
    setRuns(next);
    if (selectRunId) setSelected(next.find((run) => run.run_id === selectRunId));
    else if (!selected && next[0]) setSelected(next[0]);
  }

  useEffect(() => { refresh(); }, []);

  useEffect(() => {
    if (!selected) return;
    Promise.all([
      api.steps(selected.run_id),
      api.logs(selected.run_id),
      api.diagnoses(selected.run_id).catch(() => []),
      api.comparison(selected.run_id).catch(() => null),
      api.impact(selected.run_id).catch(() => null)
    ]).then(([nextSteps, nextLogs, nextDiagnoses, nextComparison, nextImpact]) => {
      setSteps(nextSteps);
      setLogs(nextLogs);
      setDiagnoses(nextDiagnoses);
      setComparison(nextComparison);
      setImpact(nextImpact);
    });
  }, [selected?.run_id]);

  const failedSelected = useMemo(() => selected?.status === "FAILED", [selected]);
  const successCount = runs.filter((run) => run.status === "SUCCESS").length;
  const failedCount = runs.filter((run) => run.status === "FAILED").length;

  async function replay() {
    if (!selected) return;
    const result = await api.replay(selected.run_id);
    setNotice(`Replay ${result.status}: ${result.reproduced ? "failure reproduced" : "not reproduced"}`);
    await refresh(selected.run_id);
  }

  return (
    <main>
      <header className="appHeader">
        <div>
          <span className="productMark">Runomaly</span>
          <h1>Runomaly</h1>
          <p>Likely causes, baseline comparisons, downstream impact, and replay for daily_order_analytics.</p>
        </div>
        {notice && <aside>{notice}</aside>}
      </header>
      <section className="summaryGrid">
        <article>
          <Database size={20} />
          <span>Total runs</span>
          <strong>{runs.length}</strong>
        </article>
        <article>
          <CheckCircle2 size={20} />
          <span>Successful</span>
          <strong>{successCount}</strong>
        </article>
        <article>
          <XCircle size={20} />
          <span>Failed</span>
          <strong>{failedCount}</strong>
        </article>
        <article>
          <Activity size={20} />
          <span>Selected</span>
          <strong>{selected?.status ?? "None"}</strong>
        </article>
      </section>
      <Runner onDone={(run) => { setSelected(run); refresh(run.run_id); }} />
      <RunHistory runs={runs} selected={selected?.run_id} onSelect={setSelected} onRefresh={() => refresh()} />
      <div className="split">
        <RunDetails run={selected} steps={steps} logs={logs} />
        {failedSelected ? <Investigation run={selected} diagnoses={diagnoses} comparison={comparison} impact={impact} onReplay={replay} /> : <section className="panel empty">Investigation appears when a run fails.</section>}
      </div>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
