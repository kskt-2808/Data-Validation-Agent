export const isNumeric = (v) => v !== "" && v != null && Number.isFinite(Number(v));

export function fmtNumber(v, maxDigits = 2) {
  if (v == null || !Number.isFinite(v)) return "—";
  return v.toLocaleString("en-US", { minimumFractionDigits: Math.min(2, maxDigits), maximumFractionDigits: maxDigits });
}

// Backend timestamps are ISO strings already in site time, e.g. 2026-09-14T07:00:31+05:30.
export const fmtTime = (iso) => (iso ? iso.slice(11, 19) : "");

export function fmtDate(isoDate) {
  const [y, m, d] = isoDate.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-US", { month: "short", day: "2-digit", year: "numeric" });
}

const STATUS_LABELS = { PASS: "PASS", WARN: "WARN", NO_DATA: "NO DATA", ERROR: "ERROR" };

export function renderCell(row, col) {
  const v = row[col.key];
  switch (col.type) {
    case "number":
      return v == null ? (
        "—"
      ) : (
        <>
          {fmtNumber(v)}
          {col.timeKey && row[col.timeKey] && <span className="t"> ({fmtTime(row[col.timeKey])})</span>}
        </>
      );
    case "integer":
      return v == null ? "—" : fmtNumber(v, 0);
    case "factor":
      return v == null ? "—" : v.toLocaleString("en-US", { maximumFractionDigits: 6 });
    case "output":
      if (row.status === "NO_DATA") return <strong className="nodata">NO DATA</strong>;
      return v == null ? "—" : `${fmtNumber(v)} ${row.unit || ""}`.trim();
    case "status":
      return (
        <>
          <span className={`badge ${row.status}`}>{STATUS_LABELS[row.status] || row.status}</span>
          {row.notes?.length > 0 && <div className="notes">{row.notes.join(" · ")}</div>}
        </>
      );
    default:
      return v ?? "—";
  }
}
