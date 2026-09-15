import { useEffect, useRef, useState } from "react";

const MAX_SHOWN = 200;

export default function MultiSelect({ options, value, onChange, placeholder, disabled, ariaLabel }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const ref = useRef(null);

  useEffect(() => {
    const close = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const selected = new Set(value);
  const labels = new Map(options.map((o) => [o.value, o.label]));
  const q = query.trim().toLowerCase();
  const matches = options.filter((o) => `${o.label} ${o.hint || ""}`.toLowerCase().includes(q));
  const toggle = (v) => onChange(selected.has(v) ? value.filter((x) => x !== v) : [...value, v]);

  return (
    <div className={`ms${disabled ? " disabled" : ""}`} ref={ref}>
      <div className="ms-control" onClick={() => !disabled && setOpen(true)}>
        {value.map((v) => (
          <span className="chip" key={v}>
            {labels.get(v) || v}
            <button
              type="button"
              aria-label={`Remove ${v}`}
              onClick={(e) => {
                e.stopPropagation();
                toggle(v);
              }}
            >
              ×
            </button>
          </span>
        ))}
        <input
          aria-label={ariaLabel}
          value={query}
          disabled={disabled}
          placeholder={value.length ? "" : placeholder}
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onKeyDown={(e) => {
            if (e.key === "Backspace" && !query && value.length) onChange(value.slice(0, -1));
            if (e.key === "Escape") setOpen(false);
            if (e.key === "Enter" && matches.length) {
              e.preventDefault();
              toggle(matches[0].value);
              setQuery("");
            }
          }}
        />
      </div>
      {open && !disabled && (
        <ul className="ms-menu" role="listbox" aria-multiselectable="true">
          {matches.slice(0, MAX_SHOWN).map((o) => (
            <li
              key={o.value}
              role="option"
              aria-selected={selected.has(o.value)}
              className={selected.has(o.value) ? "on" : ""}
              onMouseDown={(e) => {
                e.preventDefault();
                toggle(o.value);
              }}
            >
              <input type="checkbox" readOnly tabIndex={-1} checked={selected.has(o.value)} />
              <span>{o.label}</span>
              {o.hint && <small>{o.hint}</small>}
            </li>
          ))}
          {matches.length > MAX_SHOWN && <li className="empty">{matches.length - MAX_SHOWN} more — keep typing to narrow</li>}
          {!matches.length && <li className="empty">No matches</li>}
        </ul>
      )}
    </div>
  );
}
