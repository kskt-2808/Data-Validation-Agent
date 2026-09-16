import { Fragment, useState } from "react";
import { api, AuthError } from "../api.js";
import { fmtDate, fmtNumber, renderCell } from "../format.jsx";

export default function Results({ result, onAuthLost }) {
  const [groupBy, setGroupBy] = useState("date");
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const { formula, params } = result;

  async function download() {
    setExporting(true);
    setExportError("");
    try {
      const res = await api.exportExcel(result);
      const name = /filename="?([^";]+)"?/.exec(res.headers.get("Content-Disposition") || "")?.[1];
      const url = URL.createObjectURL(await res.blob());
      const a = Object.assign(document.createElement("a"), { href: url, download: name || "newton-report.xlsx" });
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      if (err instanceof AuthError) onAuthLost(err.message);
      else setExportError(err.message);
    } finally {
      setExporting(false);
    }
  }

  return (
    <section className="card results">
      <div className="results-head">
        <div>
          <h2>{formula.label}</h2>
          <p className="muted small">
            {fmtDate(params.from)} to {fmtDate(params.to)} · shift {params.shift} ({result.timezone})
          </p>
        </div>
        <button className="btn" type="button" onClick={download} disabled={exporting}>
          {exporting ? "Preparing…" : "Download Excel report (.xlsx)"}
        </button>
      </div>
      {exportError && <div className="alert error">{exportError}</div>}

      <h3>Audit summary</h3>
      {result.summary.map((g) => (
        <SummaryGroup key={g.unit} group={g} formula={formula} showUnit={result.summary.length > 1} />
      ))}

      <div className="ledger-head">
        <h3>Validation ledger</h3>
        <div className="inline" role="radiogroup" aria-label="View mode">
          <span>View mode</span>
          <label className="radio">
            <input type="radio" checked={groupBy === "date"} onChange={() => setGroupBy("date")} /> Group by date
          </label>
          <label className="radio">
            <input type="radio" checked={groupBy === "device"} onChange={() => setGroupBy("device")} /> Group by device
          </label>
        </div>
      </div>
      <Ledger rows={result.rows} columns={formula.columns} groupBy={groupBy} />
    </section>
  );
}

function SummaryGroup({ group, formula, showUnit }) {
  const unit = group.unit ? ` ${group.unit}` : "";
  const { PASS, WARN, NO_DATA, ERROR } = group.counts;
  const peak = group.peak;
  return (
    <>
      {showUnit && <p className="muted small group-label">Figures in {group.unit || "(no unit)"}</p>}
      <div className="cards">
        {formula.aggregate === "sum" && <Card label={formula.labels.total} value={group.total == null ? "—" : `${fmtNumber(group.total)}${unit}`} />}
        <Card
          label={formula.labels.avg}
          value={group.mean == null ? "—" : `${fmtNumber(group.mean)}${unit}`}
          sub={`across ${group.valueCount} shift${group.valueCount === 1 ? "" : "s"} with data`}
        />
        <Card
          label={formula.labels.peak}
          value={peak ? `${fmtNumber(peak.value)}${unit}` : "—"}
          sub={peak ? `${fmtDate(peak.date)} · ${peak.devID} / ${peak.sensor}` : ""}
        />
        <Card
          label="Data coverage / drops"
          tone={NO_DATA || ERROR ? "bad" : WARN ? "warn" : "good"}
          value={`${PASS + WARN} of ${group.shifts} shifts valid`}
          sub={[NO_DATA && `${NO_DATA} no data`, ERROR && `${ERROR} fetch error${ERROR === 1 ? "" : "s"}`, WARN && `${WARN} with warnings`]
            .filter(Boolean)
            .join(" · ") || "no drops"}
        />
      </div>
    </>
  );
}

function Card({ label, value, sub, tone = "" }) {
  return (
    <div className={`stat ${tone}`}>
      <span className="label">{label}</span>
      <strong>{value}</strong>
      {sub && <span className="muted small">{sub}</span>}
    </div>
  );
}

const byDate = (a, b) => a.date.localeCompare(b.date) || a.devID.localeCompare(b.devID) || a.sensor.localeCompare(b.sensor);
const byDevice = (a, b) => a.devID.localeCompare(b.devID) || a.sensor.localeCompare(b.sensor) || a.date.localeCompare(b.date);
const NUMERIC = new Set(["number", "integer", "factor", "output"]);

function Ledger({ rows, columns, groupBy }) {
  const sorted = [...rows].sort(groupBy === "device" ? byDevice : byDate);
  const groupOf = (r) => (groupBy === "device" ? `${r.devID} / ${r.sensor}` : r.date);
  return (
    <div className="table-wrap">
      <table className="ledger">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={NUMERIC.has(c.type) ? "num" : ""}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((r, i) => {
            const group = groupOf(r);
            const newGroup = i === 0 || groupOf(sorted[i - 1]) !== group;
            return (
              <Fragment key={`${r.date}|${r.devID}|${r.sensor}`}>
                {newGroup && (
                  <tr className="group">
                    <td colSpan={columns.length}>{groupBy === "device" ? group : fmtDate(group)}</td>
                  </tr>
                )}
                <tr>
                  {columns.map((c) => (
                    <td key={c.key} className={NUMERIC.has(c.type) ? "num" : c.type === "status" ? "status" : ""}>
                      {renderCell(r, c)}
                    </td>
                  ))}
                </tr>
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
