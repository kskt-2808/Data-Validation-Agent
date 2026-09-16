import { useState } from "react";
import { api, AuthError } from "../api.js";

const EXAMPLES = [
  ["delta", "Consumption from a totaliser: last reading − first, calibrated"],
  ["hours_above(140)", "Run-hours above 140 A"],
  ["integral(3600)", "Volume from a rate in m³/h"],
  ["mean / max_reading * 100", "Load factor"],
  ["hours_above(140) / 12 * 100", "Availability against a 12-hour plan"],
];

export default function CustomFormulaEditor({ help, onSaved, onCancel, onAuthLost }) {
  const [form, setForm] = useState({ label: "", expression: "", unit: "", aggregate: "sum", notes: "" });
  const [state, setState] = useState("idle"); // idle | checking | checked | saving
  const [error, setError] = useState("");
  const [checked, setChecked] = useState("");
  const set = (patch) => {
    setForm((f) => ({ ...f, ...patch }));
    setError("");
    setChecked("");
  };

  async function check() {
    if (!form.expression.trim()) return;
    setState("checking");
    setError("");
    try {
      const { uses } = await api.checkExpression(form.expression);
      setChecked(uses.length ? `Valid. Uses ${uses.join(", ")}.` : "Valid.");
      setState("checked");
    } catch (err) {
      if (err instanceof AuthError) onAuthLost(err.message);
      else setError(err.message);
      setState("idle");
    }
  }

  async function save() {
    setState("saving");
    setError("");
    try {
      onSaved(await api.createFormula(form));
    } catch (err) {
      if (err instanceof AuthError) onAuthLost(err.message);
      else {
        setError(err.message);
        setState("idle");
      }
    }
  }

  return (
    <div className="editor">
      <h3>Write a custom formula</h3>
      <p className="help">
        Arithmetic over the values Newton computes for each shift. Calibration is already applied, so
        <code> delta </code> is the calibrated consumption; use <code>delta_raw</code> for the meter's own
        difference. Saved formulas are marked as custom on every report, because they have not been reviewed
        like the built-in ones.
      </p>

      <div className="grid two">
        <label className="field">
          <span className="label">Name</span>
          <input type="text" maxLength={60} value={form.label} placeholder="Night flow"
                 onChange={(e) => set({ label: e.target.value })} />
        </label>
        <label className="field">
          <span className="label">Unit shown on the report</span>
          <input type="text" maxLength={16} value={form.unit} placeholder="m3, kWh, h, %"
                 onChange={(e) => set({ unit: e.target.value })} />
        </label>
      </div>

      <label className="field">
        <span className="label">Expression</span>
        <input type="text" className="expression" value={form.expression} placeholder="hours_above(140)"
               onChange={(e) => set({ expression: e.target.value })} onBlur={check} />
      </label>
      {checked && <p className="checked">{checked}</p>}
      {error && <div className="alert error">{error}</div>}

      <div className="row wrap">
        <label className="inline">
          <span>Across shifts, the total is</span>
          <select value={form.aggregate} onChange={(e) => set({ aggregate: e.target.value })}>
            <option value="sum">added up (consumption, hours)</option>
            <option value="mean">averaged (ratios, percentages)</option>
          </select>
        </label>
      </div>

      <label className="field">
        <span className="label">Note for whoever reads the report (optional)</span>
        <input type="text" maxLength={200} value={form.notes} placeholder="Why this exists, or where the threshold came from"
               onChange={(e) => set({ notes: e.target.value })} />
      </label>

      <details className="cheatsheet">
        <summary>What you can write</summary>
        <div className="grid two">
          <div>
            <span className="label">Examples</span>
            <ul>
              {EXAMPLES.map(([expression, meaning]) => (
                <li key={expression}>
                  <button type="button" className="link" onClick={() => set({ expression })}>{expression}</button>
                  <small>{meaning}</small>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <span className="label">Values and functions</span>
            <ul className="names">
              {Object.entries({ ...(help?.values || {}), ...(help?.functions || {}) }).map(([name, meaning]) => (
                <li key={name}>
                  <code>{name}</code>
                  <small>{meaning}</small>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </details>

      <div className="editor-actions">
        <button className="btn primary" type="button" disabled={state === "saving" || !form.label.trim() || !form.expression.trim()} onClick={save}>
          {state === "saving" ? "Saving…" : "Save formula"}
        </button>
        <button className="btn" type="button" onClick={check} disabled={state === "checking"}>Check expression</button>
        <button className="btn" type="button" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}
