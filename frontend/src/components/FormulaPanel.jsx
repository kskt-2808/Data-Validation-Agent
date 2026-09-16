import { useState } from "react";
import { isNumeric } from "../format.jsx";

// Everything here is rendered from what the formula declares in formulas.json:
// its formula, its parameters and whether its unit can be converted.
export default function FormulaPanel({
  formulas,
  formula,
  onFormula,
  targets,
  targetParams,
  setTargetParams,
  runParams,
  setRunParams,
  baseUnit,
  unitOptions,
  mixedUnits,
}) {
  const update = (key, patch) => setTargetParams((p) => ({ ...p, [key]: { ...p[key], ...patch } }));
  const runSpecs = formula.params.filter((p) => p.scope === "run");
  const targetSpecs = formula.params.filter((p) => p.scope === "target");

  return (
    <section className="card">
      <h2>
        <span className="step">3</span>Formula registry
      </h2>

      <label className="field">
        <span className="label">Select formula</span>
        <select value={formula.id} onChange={(e) => onFormula(e.target.value)}>
          {formulas.map((r) => (
            <option key={r.id} value={r.id} disabled={!r.available}>
              [{r.group}] {r.label}
              {r.available ? "" : " — coming soon"}
            </option>
          ))}
          <option disabled>+ Register new custom formula… — coming soon</option>
        </select>
      </label>

      <div className="formula">
        <span className="label">Active formula expression</span>
        <code>{formula.expression}</code>
        <p className="muted small">{formula.method}</p>
      </div>

      {runSpecs.length > 0 && (
        <div className="run-params">
          {runSpecs.map((spec) => (
            <div className="param" key={spec.key}>
              <label>
                <span className="label">{spec.label}</span>
                {spec.type === "unit" ? (
                  <select
                    value={runParams.outputUnit || ""}
                    disabled={!unitOptions.length}
                    onChange={(e) => setRunParams((p) => ({ ...p, outputUnit: e.target.value }))}
                  >
                    <option value="">Native{baseUnit ? ` (${baseUnit})` : ""}</option>
                    {unitOptions.map((u) => (
                      <option key={u} value={u}>
                        {u}
                      </option>
                    ))}
                  </select>
                ) : spec.type === "text" ? (
                  <input
                    type="text"
                    maxLength={24}
                    placeholder={spec.placeholder || "e.g. m3"}
                    value={runParams[spec.key] ?? ""}
                    onChange={(e) => setRunParams((p) => ({ ...p, [spec.key]: e.target.value }))}
                  />
                ) : (
                  <input
                    type="number"
                    step="any"
                    min={spec.min}
                    max={spec.max}
                    className="narrow"
                    placeholder={spec.default ?? "auto"}
                    value={runParams[spec.key] ?? ""}
                    onChange={(e) => setRunParams((p) => ({ ...p, [spec.key]: e.target.value }))}
                  />
                )}
              </label>
              <p className="help">
                {spec.type === "unit" && mixedUnits
                  ? "The selected sensors report in different units, so only their own units can be used."
                  : spec.type === "unit" && !unitOptions.length && baseUnit
                    ? `No conversions are defined for ${baseUnit}.`
                    : spec.help}
              </p>
            </div>
          ))}
        </div>
      )}

      <span className="label">Per-device parameters</span>
      {!targets.length ? (
        <p className="muted small">
          Choose devices and sensors to set calibration{targetSpecs.length ? " and thresholds" : ""}.
        </p>
      ) : (
        <div className="table-wrap">
          <table className="params">
            <thead>
              <tr>
                <th>Device</th>
                <th>Sensor</th>
                <th className="num">Calibration m</th>
                <th className="num">c</th>
                <th>Override</th>
                {targetSpecs.map((spec) => (
                  <th key={spec.key}>
                    {spec.label}
                    <ApplyToAll spec={spec} targets={targets} update={update} />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {targets.map((t) => {
                const values = targetParams[t.key] || {};
                return (
                  <tr key={t.key}>
                    <td>{t.devID}</td>
                    <td>
                      {t.sensor.id} · {t.sensor.name}
                      {t.sensor.unit && <span className="muted"> ({t.sensor.unit})</span>}
                    </td>
                    <td className="num">
                      {values.overrideFactor ? (
                        <input
                          type="number"
                          step="any"
                          className="narrow"
                          aria-label={`m for ${t.key}`}
                          value={values.m}
                          onChange={(e) => update(t.key, { m: e.target.value })}
                        />
                      ) : (
                        <>
                          {t.sensor.m} <span className="tag">auto</span>
                        </>
                      )}
                    </td>
                    <td className="num">
                      {values.overrideFactor ? (
                        <input
                          type="number"
                          step="any"
                          className="narrow"
                          aria-label={`c for ${t.key}`}
                          value={values.c}
                          onChange={(e) => update(t.key, { c: e.target.value })}
                        />
                      ) : (
                        t.sensor.c
                      )}
                    </td>
                    <td>
                      <input
                        type="checkbox"
                        aria-label={`Override calibration for ${t.key}`}
                        checked={!!values.overrideFactor}
                        onChange={(e) =>
                          update(
                            t.key,
                            e.target.checked
                              ? { overrideFactor: true, m: values.m ?? t.sensor.m, c: values.c ?? t.sensor.c }
                              : { overrideFactor: false },
                          )
                        }
                      />
                    </td>
                    {targetSpecs.map((spec) => (
                      <td key={spec.key}>
                        <input
                          type="number"
                          step="any"
                          className="narrow"
                          placeholder={spec.required ? "required" : "optional"}
                          aria-label={`${spec.label} for ${t.key}`}
                          value={values[spec.key] ?? ""}
                          onChange={(e) => update(t.key, { [spec.key]: e.target.value })}
                        />{" "}
                        {spec.unitFrom === "sensor" && <span className="muted small">{t.sensor.unit}</span>}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {targetSpecs.map((spec) => (
        <p className="help" key={spec.key}>
          <strong>{spec.label}:</strong> {spec.help}
        </p>
      ))}
    </section>
  );
}

function ApplyToAll({ spec, targets, update }) {
  const [value, setValue] = useState("");
  return (
    <span className="apply-all">
      <input
        type="number"
        step="any"
        className="narrow"
        placeholder="all"
        aria-label={`${spec.label} for all devices`}
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />
      <button
        type="button"
        className="btn small"
        disabled={!isNumeric(value)}
        onClick={() => targets.forEach((t) => update(t.key, { [spec.key]: value }))}
      >
        Apply to all
      </button>
    </span>
  );
}
