import { useState } from "react";
import { isNumeric } from "../format.jsx";

export default function RecipePanel({
  recipes,
  recipe,
  onRecipe,
  targets,
  overrides,
  setOverrides,
  unitScale,
  setUnitScale,
  maxGapMinutes,
  setMaxGapMinutes,
}) {
  const [allThreshold, setAllThreshold] = useState("");
  const update = (key, patch) => setOverrides((o) => ({ ...o, [key]: { ...o[key], ...patch } }));
  const effectiveM = (t) => (overrides[t.key]?.overrideFactor ? Number(overrides[t.key].m) : t.sensor.m);
  const doubleScaling = recipe.usesUnitScale && unitScale !== 1 && targets.some((t) => effectiveM(t) !== 1);

  return (
    <section className="card">
      <h2>
        <span className="step">3</span>Compute logic registry
      </h2>

      <label className="field">
        <span className="label">Select calculation recipe</span>
        <select value={recipe.id} onChange={(e) => onRecipe(e.target.value)}>
          {recipes.map((r) => (
            <option key={r.id} value={r.id} disabled={!r.available}>
              [{r.group}] {r.label}
              {r.available ? "" : " — coming soon"}
            </option>
          ))}
          <option disabled>+ Register new custom recipe… — coming soon</option>
        </select>
      </label>

      <div className="formula">
        <span className="label">Active formula expression</span>
        <code>{recipe.formula}</code>
        <p className="muted small">{recipe.method}</p>
      </div>

      <div className="row wrap params-top">
        {recipe.usesUnitScale && (
          <div className="inline" role="radiogroup" aria-label="Unit normalization">
            <span>Unit normalization</span>
            <label className="radio">
              <input type="radio" checked={unitScale === 1} onChange={() => setUnitScale(1)} /> Native unit
            </label>
            <label className="radio">
              <input type="radio" checked={unitScale === 1000} onChange={() => setUnitScale(1000)} /> ÷ 1000 (Wh → kWh)
            </label>
          </div>
        )}
        <label className="inline">
          <span>Max gap</span>
          <input
            type="number"
            min="1"
            step="1"
            className="narrow"
            value={maxGapMinutes}
            onChange={(e) => setMaxGapMinutes(e.target.value)}
          />
          <span className="muted small">min — a reading counts for at most this long</span>
        </label>
      </div>
      {doubleScaling && (
        <div className="alert warn">
          Some sensors already have m ≠ 1. If m converts Wh to kWh, dividing by 1000 again under-reports by 1000×.
        </div>
      )}

      <span className="label">Dynamic parameters</span>
      {!targets.length ? (
        <p className="muted small">Choose devices and sensors to set calibration{recipe.needsThreshold ? " and thresholds" : ""}.</p>
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
                {recipe.needsThreshold && (
                  <th>
                    Run threshold (≥)
                    <span className="apply-all">
                      <input
                        type="number"
                        step="any"
                        className="narrow"
                        placeholder="all"
                        aria-label="Threshold for all devices"
                        value={allThreshold}
                        onChange={(e) => setAllThreshold(e.target.value)}
                      />
                      <button
                        type="button"
                        className="btn small"
                        disabled={!isNumeric(allThreshold)}
                        onClick={() => targets.forEach((t) => update(t.key, { threshold: allThreshold }))}
                      >
                        Apply to all
                      </button>
                    </span>
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {targets.map((t) => {
                const o = overrides[t.key] || {};
                return (
                  <tr key={t.key}>
                    <td>{t.devID}</td>
                    <td>
                      {t.sensor.id} · {t.sensor.name}
                      {t.sensor.unit && <span className="muted"> ({t.sensor.unit})</span>}
                    </td>
                    <td className="num">
                      {o.overrideFactor ? (
                        <input type="number" step="any" className="narrow" aria-label={`m for ${t.key}`} value={o.m} onChange={(e) => update(t.key, { m: e.target.value })} />
                      ) : (
                        <>
                          {t.sensor.m} <span className="tag">auto</span>
                        </>
                      )}
                    </td>
                    <td className="num">
                      {o.overrideFactor ? (
                        <input type="number" step="any" className="narrow" aria-label={`c for ${t.key}`} value={o.c} onChange={(e) => update(t.key, { c: e.target.value })} />
                      ) : (
                        t.sensor.c
                      )}
                    </td>
                    <td>
                      <input
                        type="checkbox"
                        aria-label={`Override calibration for ${t.key}`}
                        checked={!!o.overrideFactor}
                        onChange={(e) =>
                          update(t.key, e.target.checked ? { overrideFactor: true, m: o.m ?? t.sensor.m, c: o.c ?? t.sensor.c } : { overrideFactor: false })
                        }
                      />
                    </td>
                    {recipe.needsThreshold && (
                      <td>
                        <input
                          type="number"
                          step="any"
                          className="narrow"
                          placeholder="e.g. 140"
                          aria-label={`Threshold for ${t.key}`}
                          value={o.threshold ?? ""}
                          onChange={(e) => update(t.key, { threshold: e.target.value })}
                        />{" "}
                        <span className="muted small">{t.sensor.unit}</span>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
