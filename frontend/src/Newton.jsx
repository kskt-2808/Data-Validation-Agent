import { Fragment, useEffect, useMemo, useState } from "react";
import { api, AuthError } from "./api.js";
import { isNumeric } from "./format.jsx";
import Intro from "./components/Intro.jsx";
import { Logo } from "./components/Icons.jsx";
import MultiSelect from "./components/MultiSelect.jsx";
import FormulaPanel from "./components/FormulaPanel.jsx";
import Results from "./components/Results.jsx";
import Feedback from "./components/Feedback.jsx";

const SCOPES = [
  { id: "devices", label: "Devices (Multi)", available: true },
  { id: "clusters", label: "Clusters", available: false },
  { id: "dashboards", label: "Dashboards / Widgets", available: false },
];
const PAGES = [
  { id: "intro", label: "Newton" },
  { id: "setup", label: "Setup" },
  { id: "results", label: "Results" },
];

function daysAgo(n) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toLocaleDateString("en-CA"); // YYYY-MM-DD
}

export default function Newton({ onAuthLost }) {
  const [page, setPage] = useState("intro");
  const [devices, setDevices] = useState(null);
  const [formulas, setFormulas] = useState([]);
  const [unitConversions, setUnitConversions] = useState({});
  const [timezone, setTimezone] = useState("");
  const [loadError, setLoadError] = useState("");

  const [deviceIds, setDeviceIds] = useState([]);
  const [sensorIds, setSensorIds] = useState([]);
  const [from, setFrom] = useState(daysAgo(7));
  const [to, setTo] = useState(daysAgo(1));
  const [shiftStart, setShiftStart] = useState("07:00");
  const [shiftEnd, setShiftEnd] = useState("07:00");
  const [formulaId, setFormulaId] = useState("consumption_delta");
  const [runParams, setRunParams] = useState({});
  const [targetParams, setTargetParams] = useState({});

  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState("");
  const [result, setResult] = useState(null);

  const fail = (err, setter) => (err instanceof AuthError ? onAuthLost(err.message) : setter(err.message));

  useEffect(() => {
    Promise.all([api.devices(), api.formulas()])
      .then(([d, r]) => {
        setDevices(d.devices);
        setFormulas(r.formulas);
        setUnitConversions(r.unitConversions || {});
        setTimezone(r.timezone);
      })
      .catch((err) => fail(err, setLoadError));
  }, []);

  const formula = formulas.find((r) => r.id === formulaId);

  // Parameters come from the formula registry, so switching formula re-renders the
  // inputs; values shared by both formulas (gap tolerance) are kept.
  useEffect(() => {
    if (!formula) return;
    setRunParams((prev) => {
      const next = {};
      for (const spec of formula.params.filter((p) => p.scope === "run")) {
        next[spec.key] = prev[spec.key] ?? (spec.default ?? "");
      }
      return next;
    });
  }, [formulaId, formulas.length]);

  const deviceById = useMemo(() => new Map((devices || []).map((d) => [d.devID, d])), [devices]);

  const deviceOptions = useMemo(
    () =>
      (devices || []).map((d) => ({
        value: d.devID,
        label: d.devID,
        hint: [d.devName !== d.devID && d.devName, d.devType].filter(Boolean).join(" · "),
      })),
    [devices],
  );

  // Sensor IDs are per device: D25 can be energy on one meter and power factor on another.
  const sensorOptions = useMemo(() => {
    const byId = new Map();
    for (const devID of deviceIds) {
      for (const s of deviceById.get(devID)?.sensors || []) {
        const entry = byId.get(s.id) || { value: s.id, names: new Set(), unit: s.unit, count: 0 };
        entry.names.add(s.name);
        entry.count += 1;
        byId.set(s.id, entry);
      }
    }
    return [...byId.values()].map((e) => {
      const [name] = e.names;
      const hints = [];
      if (deviceIds.length > 1) hints.push(`on ${e.count} of ${deviceIds.length} devices`);
      if (e.names.size > 1) hints.push("name differs by device");
      return { value: e.value, label: `${e.value} - ${name}${e.unit ? ` (${e.unit})` : ""}`, hint: hints.join(" · ") };
    });
  }, [deviceIds, deviceById]);

  const targets = useMemo(() => {
    const out = [];
    for (const devID of deviceIds) {
      const device = deviceById.get(devID);
      for (const sid of sensorIds) {
        const sensor = device?.sensors.find((s) => s.id === sid);
        if (sensor) out.push({ key: `${devID}|${sid}`, devID, sensor });
      }
    }
    return out;
  }, [deviceIds, sensorIds, deviceById]);

  // A conversion is only offered when every selected sensor shares one unit.
  const sensorUnits = [...new Set(targets.map((t) => t.sensor.unit || ""))];
  const unitSource = formula?.unit?.source;
  const baseUnit =
    unitSource === "hours" ? "h" : unitSource === "percent" ? "%" : sensorUnits.length === 1 ? sensorUnits[0] : null;
  const unitOptions = baseUnit ? Object.keys(unitConversions[baseUnit] || {}) : [];
  const mixedUnits = unitSource === "sensor" && sensorUnits.length > 1;

  const runSpecs = formula?.params.filter((p) => p.scope === "run") || [];
  const targetSpecs = formula?.params.filter((p) => p.scope === "target") || [];

  const blocker = (() => {
    if (!formula) return "Loading formulas…";
    if (!targets.length) return "Choose at least one device and a sensor it has.";
    if (!from || !to) return "Pick a date range.";
    if (to < from) return "The end date is before the start date.";
    for (const spec of runSpecs) {
      const value = runParams[spec.key];
      if (spec.type !== "number") continue;
      if (value === "" || value == null) {
        if (spec.required) return `${spec.label} is required.`;
        continue;
      }
      if (!isNumeric(value)) return `${spec.label} must be a number.`;
    }
    for (const spec of targetSpecs) {
      if (!spec.required) continue;
      if (targets.some((t) => !isNumeric(targetParams[t.key]?.[spec.key])))
        return `Set ${spec.label.toLowerCase()} for every device.`;
    }
    if (
      targets.some((t) => {
        const v = targetParams[t.key];
        return v?.overrideFactor && (!isNumeric(v.m) || Number(v.m) === 0 || !isNumeric(v.c));
      })
    )
      return "An overridden calibration needs a numeric m (not 0) and c.";
    return "";
  })();

  async function run() {
    setRunning(true);
    setRunError("");
    try {
      const body = { formula: formulaId, from, to, shiftStart, shiftEnd, targets: [] };
      for (const spec of runSpecs) {
        const value = runParams[spec.key];
        if (value === "" || value == null) continue;
        body[spec.key] = spec.type === "number" ? Number(value) : value;
      }
      body.targets = targets.map((t) => {
        const v = targetParams[t.key] || {};
        const target = { devID: t.devID, sensor: t.sensor.id };
        if (v.overrideFactor) Object.assign(target, { m: Number(v.m), c: Number(v.c) });
        for (const spec of targetSpecs) {
          if (isNumeric(v[spec.key])) target[spec.key] = Number(v[spec.key]);
        }
        return target;
      });
      setResult(await api.validate(body));
      setPage("results");
    } catch (err) {
      fail(err, setRunError);
    } finally {
      setRunning(false);
    }
  }

  const shiftCount = from && to && to >= from ? Math.round((new Date(to) - new Date(from)) / 86400000) + 1 : 0;

  return (
    <div className="app">
      <header className="topbar">
        <Logo className="brand-mark" />
        <nav className="stepper" aria-label="Pages">
          {PAGES.map((p, i) => (
            <Fragment key={p.id}>
              {i > 0 && <span className="step-dash" aria-hidden="true" />}
              <button
                type="button"
                className={`step-tab${page === p.id ? " on" : ""}`}
                disabled={p.id === "results" && !result}
                onClick={() => setPage(p.id)}
              >
                <span className="num">{i + 1}</span>
                <span>{p.label}</span>
              </button>
            </Fragment>
          ))}
        </nav>
      </header>

      {loadError && <div className="alert error">{loadError}</div>}

      {page === "intro" && (
        <Intro
          formulas={formulas}
          onStart={() => setPage("setup")}
          onPick={(id) => {
            setFormulaId(id);
            setPage("setup");
          }}
        />
      )}

      {page === "setup" && (
        <div className="page">
          <section className="card">
            <h2>
              <span className="step">1</span>Target selection
            </h2>
            <div className="scope" role="radiogroup" aria-label="Scope">
              {SCOPES.map((s) => (
                <label key={s.id} className={`radio${s.available ? "" : " disabled"}`}>
                  <input type="radio" name="scope" checked={s.id === "devices"} disabled={!s.available} readOnly />
                  {s.label}
                  {!s.available && <em className="soon">Phase 2</em>}
                </label>
              ))}
            </div>
            <div className="grid two">
              <div className="field">
                <span className="label">Select devices</span>
                <MultiSelect
                  ariaLabel="Devices"
                  options={deviceOptions}
                  value={deviceIds}
                  onChange={setDeviceIds}
                  disabled={!devices}
                  placeholder={devices ? "Search devices…" : loadError ? "Devices unavailable" : "Loading devices…"}
                />
              </div>
              <div className="field">
                <span className="label">Filter & select sensors</span>
                <MultiSelect
                  ariaLabel="Sensors"
                  options={sensorOptions}
                  value={sensorIds.filter((id) => sensorOptions.some((o) => o.value === id))}
                  onChange={setSensorIds}
                  disabled={!deviceIds.length}
                  placeholder={deviceIds.length ? "Search sensors…" : "Choose devices first"}
                />
              </div>
            </div>
            {targets.length > 0 && (
              <p className="muted small">
                {targets.length} device–sensor pair{targets.length === 1 ? "" : "s"} selected
              </p>
            )}
          </section>

          <section className="card">
            <h2>
              <span className="step">2</span>Shift & timeframe
            </h2>
            <div className="row wrap">
              <div className="inline">
                <span>Date range</span>
                <input type="date" aria-label="From date" value={from} max={to} onChange={(e) => setFrom(e.target.value)} />
                <span>to</span>
                <input type="date" aria-label="To date" value={to} min={from} onChange={(e) => setTo(e.target.value)} />
              </div>
              <div className="inline">
                <span>Shift timing</span>
                <input type="time" aria-label="Shift start" value={shiftStart} onChange={(e) => setShiftStart(e.target.value)} />
                <span>to</span>
                <input type="time" aria-label="Shift end" value={shiftEnd} onChange={(e) => setShiftEnd(e.target.value)} />
                {shiftEnd <= shiftStart && <span className="pill">+1 day</span>}
              </div>
            </div>
            <p className="help">
              Times are {timezone || "site time"}. Each shift runs from its start up to, but not including, its end, so a
              reading stamped exactly at the end counts toward the next shift.
            </p>
          </section>

          {formula && (
            <FormulaPanel
              formulas={formulas}
              formula={formula}
              onFormula={setFormulaId}
              targets={targets}
              targetParams={targetParams}
              setTargetParams={setTargetParams}
              runParams={runParams}
              setRunParams={setRunParams}
              baseUnit={baseUnit}
              unitOptions={unitOptions}
              mixedUnits={mixedUnits}
            />
          )}

          <div className="run">
            <button className="btn primary big" type="button" disabled={!!blocker || running} onClick={run}>
              {running ? `Validating ${targets.length * shiftCount} shifts…` : "Run batch validation"}
            </button>
            {blocker && <p className="muted small">{blocker}</p>}
            {runError && <div className="alert error">{runError}</div>}
          </div>
        </div>
      )}

      {page === "results" &&
        (result ? (
          <div className="page">
            <Results result={result} onAuthLost={onAuthLost} />
            <Feedback result={result} onAuthLost={onAuthLost} />
            <div className="page-actions">
              <button className="btn" type="button" onClick={() => setPage("setup")}>
                ← Back to setup
              </button>
            </div>
          </div>
        ) : (
          <p className="page muted">Run a validation to see results.</p>
        ))}
    </div>
  );
}
