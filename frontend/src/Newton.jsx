import { useEffect, useMemo, useState } from "react";
import { api, AuthError } from "./api.js";
import { isNumeric } from "./format.jsx";
import MultiSelect from "./components/MultiSelect.jsx";
import RecipePanel from "./components/RecipePanel.jsx";
import Results from "./components/Results.jsx";

const SCOPES = [
  { id: "devices", label: "Devices (Multi)", available: true },
  { id: "clusters", label: "Clusters", available: false },
  { id: "dashboards", label: "Dashboards / Widgets", available: false },
];

function daysAgo(n) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toLocaleDateString("en-CA"); // YYYY-MM-DD
}

export default function Newton({ onAuthLost }) {
  const [devices, setDevices] = useState(null);
  const [recipes, setRecipes] = useState([]);
  const [timezone, setTimezone] = useState("");
  const [loadError, setLoadError] = useState("");

  const [deviceIds, setDeviceIds] = useState([]);
  const [sensorIds, setSensorIds] = useState([]);
  const [from, setFrom] = useState(daysAgo(7));
  const [to, setTo] = useState(daysAgo(1));
  const [shiftStart, setShiftStart] = useState("07:00");
  const [shiftEnd, setShiftEnd] = useState("07:00");
  const [recipeId, setRecipeId] = useState("consumption_delta");
  const [unitScale, setUnitScale] = useState(1);
  const [maxGapMinutes, setMaxGapMinutes] = useState("15");
  const [overrides, setOverrides] = useState({});

  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState("");
  const [result, setResult] = useState(null);

  const fail = (err, setter) => (err instanceof AuthError ? onAuthLost(err.message) : setter(err.message));

  useEffect(() => {
    Promise.all([api.devices(), api.recipes()])
      .then(([d, r]) => {
        setDevices(d.devices);
        setRecipes(r.recipes);
        setTimezone(r.timezone);
      })
      .catch((err) => fail(err, setLoadError));
  }, []);

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

  const recipe = recipes.find((r) => r.id === recipeId);
  const blocker = (() => {
    if (!targets.length) return "Choose at least one device and a sensor it has.";
    if (!from || !to) return "Pick a date range.";
    if (to < from) return "The end date is before the start date.";
    if (!isNumeric(maxGapMinutes) || Number(maxGapMinutes) <= 0) return "Max gap must be a positive number of minutes.";
    if (recipe?.needsThreshold && targets.some((t) => !isNumeric(overrides[t.key]?.threshold)))
      return "Set a run threshold for every device.";
    if (
      targets.some((t) => {
        const o = overrides[t.key];
        return o?.overrideFactor && (!isNumeric(o.m) || Number(o.m) === 0 || !isNumeric(o.c));
      })
    )
      return "An overridden calibration needs a numeric m (not 0) and c.";
    return "";
  })();

  async function run() {
    setRunning(true);
    setRunError("");
    try {
      const body = {
        recipe: recipeId,
        from,
        to,
        shiftStart,
        shiftEnd,
        unitScale: recipe.usesUnitScale ? unitScale : 1,
        maxGapMinutes: Number(maxGapMinutes),
        targets: targets.map((t) => {
          const o = overrides[t.key] || {};
          return {
            devID: t.devID,
            sensor: t.sensor.id,
            ...(o.overrideFactor ? { m: Number(o.m), c: Number(o.c) } : {}),
            ...(recipe.needsThreshold ? { threshold: Number(o.threshold) } : {}),
          };
        }),
      };
      setResult(await api.validate(body));
    } catch (err) {
      fail(err, setRunError);
    } finally {
      setRunning(false);
    }
  }

  const shiftCount = from && to && to >= from ? Math.round((new Date(to) - new Date(from)) / 86400000) + 1 : 0;

  return (
    <div className="page">
      <header className="topbar">
        <div className="brand">
          <span className="logo">iosense</span>
          <span className="divider">|</span>
          <strong>NEWTON</strong>
          <span className="muted">— Data Validation Agent</span>
        </div>
        <p className="tagline">Hi, I'm Newton. Let's crunch some numbers.</p>
      </header>

      {loadError && <div className="alert error">{loadError}</div>}

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
        <p className="muted small">
          Times are {timezone || "site time"}. Each shift runs from its start up to, but not including, its end, so a
          reading stamped exactly at the end counts toward the next shift.
        </p>
      </section>

      {recipe && (
        <RecipePanel
          recipes={recipes}
          recipe={recipe}
          onRecipe={setRecipeId}
          targets={targets}
          overrides={overrides}
          setOverrides={setOverrides}
          unitScale={unitScale}
          setUnitScale={setUnitScale}
          maxGapMinutes={maxGapMinutes}
          setMaxGapMinutes={setMaxGapMinutes}
        />
      )}

      <div className="run">
        <button className="btn primary big" type="button" disabled={!!blocker || running || !recipe} onClick={run}>
          {running ? `Validating ${targets.length * shiftCount} shifts…` : "Run batch validation"}
        </button>
        {blocker && <p className="muted small">{blocker}</p>}
        {runError && <div className="alert error">{runError}</div>}
      </div>

      {result && <Results result={result} onAuthLost={onAuthLost} />}
    </div>
  );
}
