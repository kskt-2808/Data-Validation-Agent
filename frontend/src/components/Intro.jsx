import { useEffect, useRef, useState } from "react";
import { Arrow, Bars, Bolt, Database, Document, Gauge, Grid, Layers, Lock, Logo, Pulse, ShieldCheck, Target, Trend } from "./Icons.jsx";

// Cards come from the recipe registry, so what the page advertises is what the
// app can actually run. Anything not listed here still shows, using its formula.
const CARD_COPY = {
  consumption_delta: { title: "Energy Validation", blurb: "Recompute and verify reported energy metrics.", Icon: Bolt },
  run_hours: { title: "Runtime Analytics", blurb: "Validate operational run-hours against raw readings.", Icon: Bars },
  average_value: { title: "Telemetry Averages", blurb: "Check reported averages against every reading.", Icon: Grid },
  time_weighted_avg: { title: "Trend Consistency", blurb: "Weight each reading by how long it actually held.", Icon: Trend },
  availability_ratio: { title: "OEE Availability", blurb: "Run-hours measured against planned shift hours.", Icon: Gauge },
  load_factor: { title: "Load Factor", blurb: "Average demand against the peak of the shift.", Icon: Trend },
};

const ASSURANCES = [
  { Icon: ShieldCheck, tone: "blue", title: "Recomputed from raw", blurb: "Every figure comes from raw readings." },
  { Icon: Lock, tone: "green", title: "Your own session", blurb: "Signs in as you; stores no tokens." },
  { Icon: Layers, tone: "purple", title: "Many devices at once", blurb: "A whole fleet across a date range." },
  { Icon: Document, tone: "blue", title: "Traceable", blurb: "Every result carries its evidence." },
];

export default function Intro({ recipes, onStart, onPick }) {
  const cards = recipes
    .filter((r) => r.available)
    .map((r) => ({ id: r.id, Icon: Grid, title: r.label.split(" (")[0], blurb: r.formula, ...CARD_COPY[r.id] }));
  const [active, setActive] = useState(0);
  const step = (delta) => setActive((i) => (i + delta + cards.length) % cards.length);
  const trackRef = useRef(null);

  // Keep the highlighted card in view when it changes, so the arrows and dots
  // both work on a track that holds more cards than fit.
  useEffect(() => {
    const card = trackRef.current?.children[active];
    card?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
  }, [active]);

  return (
    <div className="intro">
      <section className="hero">
        <Logo className="hero-watermark" />
        <p className="eyebrow">Newton</p>
        <h1>
          <span>Validation.</span>
          <span className="gradient">Reimagined.</span>
        </h1>

        <ul className="trust">
          <li>
            <span className="chip-icon blue">
              <Database />
            </span>
            Source-Based
          </li>
          <li>
            <span className="chip-icon green">
              <ShieldCheck />
            </span>
            Audit-Ready
          </li>
          <li>
            <span className="chip-icon purple">
              <Target />
            </span>
            Built for Accuracy
          </li>
        </ul>

        <button className="cta" type="button" onClick={onStart}>
          <span className="cta-icon">
            <Pulse />
          </span>
          Start Validation
          <span className="cta-arrow">
            <Arrow />
          </span>
        </button>

        {cards.length > 0 && (
          <div
            className="carousel"
            role="group"
            aria-roledescription="carousel"
            aria-label="What Newton validates"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "ArrowLeft") step(-1);
              if (e.key === "ArrowRight") step(1);
            }}
          >
            <button className="round-btn" type="button" aria-label="Previous" onClick={() => step(-1)}>
              <Arrow />
            </button>
            <div className="track" ref={trackRef}>
              {cards.map((card, i) => (
                <button
                  key={card.id}
                  type="button"
                  className={`cap-card${i === active ? " on" : ""}`}
                  aria-current={i === active}
                  onClick={() => (i === active ? onPick(card.id) : setActive(i))}
                >
                  <span className="cap-icon">
                    <card.Icon />
                  </span>
                  <strong>{card.title}</strong>
                  <span className="blurb">{card.blurb}</span>
                </button>
              ))}
            </div>
            <button className="round-btn" type="button" aria-label="Next" onClick={() => step(1)}>
              <Arrow />
            </button>
          </div>
        )}
        <div className="dots">
          {cards.map((card, i) => (
            <button
              key={card.id}
              type="button"
              className={i === active ? "on" : ""}
              aria-label={`Show ${card.title}`}
              onClick={() => setActive(i)}
            />
          ))}
        </div>
      </section>

      <section className="assurances">
        {ASSURANCES.map((a) => (
          <article key={a.title}>
            <span className={`tile ${a.tone}`}>
              <a.Icon />
            </span>
            <div>
              <strong>{a.title}</strong>
              <p>{a.blurb}</p>
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}
