import { useState } from "react";
import { api, AuthError } from "../api.js";

const FACES = [
  { value: 1, label: "Unhappy", mouth: "M34 62 Q50 50 66 62", tone: "bad" },
  { value: 2, label: "Poor", mouth: "M34 60 Q50 52 66 60", tone: "bad" },
  { value: 3, label: "Neutral", mouth: "M34 58h32", tone: "mid" },
  { value: 4, label: "Good", mouth: "M34 54 Q50 64 66 54", tone: "good" },
  { value: 5, label: "Great", mouth: "M32 52 Q50 70 68 52", tone: "good" },
];

export default function Feedback({ result, onAuthLost }) {
  const [rating, setRating] = useState(null);
  const [comment, setComment] = useState("");
  const [state, setState] = useState("idle"); // idle | sending | sent | error
  const [error, setError] = useState("");

  async function send() {
    setState("sending");
    setError("");
    try {
      const counts = result.summary.reduce((all, group) => {
        for (const [key, n] of Object.entries(group.counts)) all[key] = (all[key] || 0) + n;
        return all;
      }, {});
      await api.feedback({
        rating,
        comment,
        // Sent with the note so a "this looks wrong" arrives with the run it refers to.
        context: {
          formula: result.formula.id,
          from: result.params.from,
          to: result.params.to,
          shift: result.params.shift,
          targets: new Set(result.rows.map((r) => `${r.devID}|${r.sensor}`)).size,
          shifts: result.rows.length,
          counts,
        },
      });
      setState("sent");
    } catch (err) {
      if (err instanceof AuthError) onAuthLost(err.message);
      else {
        setError(err.message);
        setState("error");
      }
    }
  }

  if (state === "sent") {
    return (
      <section className="card feedback sent">
        <h2>Thank you</h2>
        <p className="muted">
          Noted, along with which report you were looking at. Run another validation any time you want to tell us more.
        </p>
      </section>
    );
  }

  return (
    <section className="card feedback">
      <h2>Submit feedback</h2>
      <div className="faces" role="radiogroup" aria-label="How was this report?">
        {FACES.map((face) => (
          <button
            key={face.value}
            type="button"
            role="radio"
            aria-checked={rating === face.value}
            aria-label={face.label}
            className={`face ${face.tone}${rating === face.value ? " on" : ""}`}
            onClick={() => setRating(face.value)}
          >
            <svg viewBox="0 0 100 100" aria-hidden="true">
              <circle cx="50" cy="50" r="34" fill="none" stroke="currentColor" strokeWidth="4" />
              <circle cx="38" cy="40" r="4.5" fill="currentColor" />
              <circle cx="62" cy="40" r="4.5" fill="currentColor" />
              <path d={face.mouth} fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
            </svg>
            <span>{face.label}</span>
          </button>
        ))}
      </div>

      <label className="field idea">
        <span className="label">Drop your idea here — let's grow together</span>
        <textarea
          rows={4}
          maxLength={2000}
          value={comment}
          placeholder="A formula you need, a number that looks wrong, anything that would make this more useful…"
          onChange={(e) => setComment(e.target.value)}
        />
      </label>

      {error && <div className="alert error">{error}</div>}
      <div className="feedback-actions">
        <button
          className="btn primary"
          type="button"
          disabled={state === "sending" || (!rating && !comment.trim())}
          onClick={send}
        >
          {state === "sending" ? "Sending…" : "Send feedback"}
        </button>
        <p className="help">
          Sent with your rating: the formula, date range and how many shifts passed. Not your readings, and not your
          sign-in token.
        </p>
      </div>
    </section>
  );
}
