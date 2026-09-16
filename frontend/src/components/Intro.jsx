// Page 1: who Newton is and what it does, before any settings.
export default function Intro({ recipes, onStart }) {
  const available = recipes.filter((r) => r.available);
  return (
    <section className="intro">
      <div className="hero">
        <p className="eyebrow">iosense · Data Validation Agent</p>
        <h1>
          Hi, I'm <strong>Newton</strong>.
        </h1>
        <p className="lede">
          I recompute your device figures from raw readings and show the arithmetic, so a number in a
          report can be checked instead of trusted.
        </p>
        <p className="crunch">Let's crunch some numbers.</p>
        <button className="btn primary big" type="button" onClick={onStart}>
          Start a validation
        </button>
      </div>

      <div className="chart-strip" aria-hidden="true">
        <DonutGlyph />
        <BarsGlyph />
        <TableGlyph />
        <LineGlyph />
      </div>

      <div className="intro-cards">
        <article>
          <h2>What I check</h2>
          <ul>
            {available.map((r) => (
              <li key={r.id}>
                <strong>{r.label.split(" (")[0]}</strong>
                <code>{r.formula}</code>
              </li>
            ))}
          </ul>
        </article>
        <article>
          <h2>How I work</h2>
          <ul className="plain">
            <li>I read raw readings and apply each sensor's calibration myself.</li>
            <li>Every row shows the readings, times and factor behind the number.</li>
            <li>A shift without enough data says NO DATA — never zero.</li>
            <li>Results download as Excel, with the method on its own sheet.</li>
          </ul>
        </article>
      </div>
    </section>
  );
}

const GLYPH = { fill: "none", stroke: "currentColor", strokeWidth: 6, strokeLinecap: "round" };

function DonutGlyph() {
  return (
    <svg viewBox="0 0 100 100" className="glyph">
      <circle cx="50" cy="50" r="32" {...GLYPH} opacity="0.25" />
      <path d="M50 18a32 32 0 0 1 28 47" {...GLYPH} />
      <path d="M22 65a32 32 0 0 1 0-30" {...GLYPH} opacity="0.6" />
    </svg>
  );
}

function BarsGlyph() {
  return (
    <svg viewBox="0 0 100 100" className="glyph">
      <path d="M22 78V54M42 78V32M62 78V44M82 78V22" {...GLYPH} strokeWidth="10" />
      <path d="M12 82h78" {...GLYPH} strokeWidth="4" opacity="0.4" />
    </svg>
  );
}

function TableGlyph() {
  return (
    <svg viewBox="0 0 100 100" className="glyph">
      <rect x="16" y="24" width="68" height="52" rx="6" {...GLYPH} strokeWidth="5" opacity="0.5" />
      <path d="M16 40h68M16 58h68M44 40v36" {...GLYPH} strokeWidth="4" opacity="0.7" />
    </svg>
  );
}

function LineGlyph() {
  return (
    <svg viewBox="0 0 100 100" className="glyph">
      <path d="M14 70l18-16 16 10 14-26 24 14" {...GLYPH} />
      <path d="M14 82h76" {...GLYPH} strokeWidth="4" opacity="0.4" />
    </svg>
  );
}
