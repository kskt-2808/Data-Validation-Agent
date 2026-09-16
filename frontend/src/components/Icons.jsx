// One stroke style for every icon, so the set reads as one family.
const S = { fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round", strokeLinejoin: "round" };

export function Logo({ className = "" }) {
  // The iosense mark: two hollow peaks whose inner legs taper into one deep point.
  return (
    <svg viewBox="0 0 200 200" className={className} aria-hidden="true">
      <path d="M68 24 L28 122 L54 132 L68 58 L100 166 L86 31 Z M132 24 L172 122 L146 132 L132 58 L100 166 L114 31 Z" fill="currentColor" />
    </svg>
  );
}

export function Bolt() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M13 2 4.5 13.5H11l-1 8.5 9-11.5h-6.5L13 2Z" fill="currentColor" />
    </svg>
  );
}

export function Bars() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 20V11M12 20V5M19 20v-6" {...S} strokeWidth="2.2" />
    </svg>
  );
}

export function Grid() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3.5" y="4.5" width="17" height="15" rx="2.5" {...S} />
      <path d="M3.5 9.5h17M3.5 14.5h17M11 9.5V20" {...S} />
    </svg>
  );
}

export function Trend() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 16.5 9 11l3.5 3L20 6.5" {...S} strokeWidth="2" />
      <path d="M15 6.5h5v5" {...S} strokeWidth="2" />
    </svg>
  );
}

export function Gauge() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 17a8 8 0 1 1 16 0" {...S} strokeWidth="2" />
      <path d="M12 17l4.5-5" {...S} strokeWidth="2" />
    </svg>
  );
}

export function Database() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <ellipse cx="12" cy="6.5" rx="7" ry="3" {...S} />
      <path d="M5 6.5v11c0 1.7 3.1 3 7 3s7-1.3 7-3v-11M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3" {...S} />
    </svg>
  );
}

export function ShieldCheck() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3l7 3v5.5c0 4.2-2.9 7.7-7 8.5-4.1-.8-7-4.3-7-8.5V6l7-3Z" {...S} />
      <path d="m9 12 2 2 4-4" {...S} />
    </svg>
  );
}

export function Target() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="7.5" {...S} />
      <circle cx="12" cy="12" r="3.5" {...S} />
      <path d="M12 2v3M12 19v3M2 12h3M19 12h3" {...S} />
    </svg>
  );
}

export function Lock() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="4.5" y="10.5" width="15" height="10" rx="2.5" {...S} />
      <path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" {...S} />
    </svg>
  );
}

export function Layers() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m12 3 8.5 4.5L12 12 3.5 7.5 12 3Z" {...S} />
      <path d="m4 12.5 8 4.3 8-4.3M4 16.8l8 4.2 8-4.2" {...S} />
    </svg>
  );
}

export function Document() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 3.5h7l5 5v12a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1v-16a1 1 0 0 1 1-1Z" {...S} />
      <path d="M13 3.5V9h5M8.5 13h7M8.5 16.5h5" {...S} />
    </svg>
  );
}

export function Pulse() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M2 12h4l2.5-6 4 12 2.5-6H22" {...S} strokeWidth="2" />
    </svg>
  );
}

export function Arrow() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 12h15M13 6l6 6-6 6" {...S} strokeWidth="2" />
    </svg>
  );
}
