import { useLayoutEffect, useRef, useState } from "react";
import { Arrow, Bars, Bolt, Database, Document, Gauge, Grid, Layers, Lock, Logo, Pulse, ShieldCheck, Target, Trend } from "./Icons.jsx";

// Cards come from the formula registry, so what the page advertises is what the
// app can actually run. Anything not listed here still shows, using its formula.
const CARD_COPY = {
  consumption_delta: { title: "Energy Validation", blurb: "Recompute and verify reported energy metrics.", Icon: Bolt },
  run_hours: { title: "Runtime Analytics", blurb: "Validate operational run-hours against raw readings.", Icon: Bars },
  average_value: { title: "Telemetry Averages", blurb: "Check reported averages against every reading.", Icon: Grid },
  time_weighted_avg: { title: "Trend Consistency", blurb: "Weight each reading by how long it actually held.", Icon: Trend },
  availability_ratio: { title: "OEE Availability", blurb: "Run-hours measured against planned shift hours.", Icon: Gauge },
  load_factor: { title: "Load Factor", blurb: "Average demand against the peak of the shift.", Icon: Trend },
  flow_volume: { title: "Flow Volume", blurb: "Volume from a flow rate, integrated over the shift.", Icon: Database },
};

// Carousel order is a product decision, not the registry's: energy validation is
// the most-used check, so it sits mid-row with cards either side and opens selected.
// Anything not listed here follows in registry order.
const CARD_ORDER = ["time_weighted_avg", "average_value", "consumption_delta", "run_hours",
                    "availability_ratio", "load_factor"];
const DEFAULT_CARD = "consumption_delta";

const ASSURANCES = [
  { Icon: ShieldCheck, tone: "blue", title: "Recomputed from raw", blurb: "Every figure comes from raw readings." },
  { Icon: Lock, tone: "green", title: "Your own session", blurb: "Signs in as you; stores no tokens." },
  { Icon: Layers, tone: "purple", title: "Many devices at once", blurb: "A whole fleet across a date range." },
  { Icon: Document, tone: "blue", title: "Traceable", blurb: "Every result carries its evidence." },
];

export default function Intro({ formulas, onStart, onPick }) {
  const cards = formulas
    .filter((r) => r.available)
    .map((r) => ({ id: r.id, Icon: Grid, title: r.label.split(" (")[0], blurb: r.expression, ...CARD_COPY[r.id] }))
    .sort((a, b) => {
      const rank = (id) => (CARD_ORDER.indexOf(id) + 1 || CARD_ORDER.length + 1);
      return rank(a.id) - rank(b.id);
    });
  const [active, setActive] = useState(0);

  // Select the default before the first paint, so the carousel opens on it
  // instead of visibly sliding there. Runs once: a later choice is the user's.
  const defaulted = useRef(false);
  useLayoutEffect(() => {
    if (defaulted.current || !cards.length) return;
    const index = cards.findIndex((card) => card.id === DEFAULT_CARD);
    if (index >= 0) setActive(index);
    defaulted.current = true;
  }, [cards.length]);
  const step = (delta) => setActive((i) => (i + delta + cards.length) % cards.length);
  const trackRef = useRef(null);
  const viewportRef = useRef(null);
  const [offset, setOffset] = useState(0);

  // The track slides as one piece, so every card can sit dead centre — including
  // the first and last, which a scrolling track can never reach.
  useLayoutEffect(() => {
    const centre = () => {
      const card = trackRef.current?.children[active];
      const viewport = viewportRef.current;
      if (!card || !viewport) return;
      setOffset(viewport.clientWidth / 2 - (card.offsetLeft + card.offsetWidth / 2));
    };
    // Measure after layout settles, or a flex viewport reports its content width.
    const frame = requestAnimationFrame(centre);
    centre();
    window.addEventListener("resize", centre);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", centre);
    };
  }, [active, cards.length]);

  return (
    <div className="intro">
      <section className="hero">
        <Logo className="hero-watermark" />
        <h1>Newton</h1>
        <p className="tagline">
          Validation. <span className="gradient">Reimagined.</span>
        </p>

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
            <div className="viewport" ref={viewportRef}>
              <div className="track" ref={trackRef} style={{ transform: `translateX(${offset}px)` }}>
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
