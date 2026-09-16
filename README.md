# Newton — Data Validation Agent

A Launchpad app that recomputes device figures from raw iosense readings and
exports an auditable Excel report. Phase 1 covers devices, per shift: energy
consumption, run-hours, averages, OEE availability and load factor.

The UI is three pages: Newton's introduction, the set-up, then the results.

## Deploy

### AI Studio Manager

AI Studio Manager has no Flask preset. Its **Next.js preset in SSR mode** is the
one that keeps a server process running, and it works for any app with root
`package.json` scripts:

| Setting | Value |
|---|---|
| Framework | **Next.js** (Create React App and Vite are static-only: the API would 404) |
| Mode | **SSR / Server-Side** |
| Install command | `npm install --force` (default) |
| Build command | `npm run build` (default) |
| Start command | `npm start` (default) |
| Repository path | empty |

The pipeline runs install → build in the repo root, then starts `npm start`
under pm2 with `PORT` set to a free port in 9000–10000, and puts an HTTPS
domain in front of it with nginx. `npm start` runs `start.sh`, which reads that
`PORT`. Register the **assigned domain** (not a port) in Launchpad.

The deploy server keeps its own clone of the repo and does not pull on a
first Deploy. After pushing, use **Update deployment** (it pulls, then
redeploys), or the deploy will build an old or empty checkout.

### Feedback settings

The Results page collects a rating and a note. Each submission appends to a
JSON-lines file and, if a webhook is set, posts to Teams or Slack.

| Variable | Meaning |
|---|---|
| `FEEDBACK_FILE` | Where to append. Default `~/newton-feedback/feedback.jsonl` — outside the repo, so a redeploy cannot erase it. |
| `FEEDBACK_WEBHOOK_URL` | Teams or Slack incoming webhook. Both accept the same payload. A failed post never loses the entry; the file is the record. |
| `FEEDBACK_ADMIN_KEY` | Enables `GET /api/feedback/export.csv?key=…`. Unset means the export returns 404. |

Stored with each submission: the rating, the note, and the run it came from
(formula, date range, shift, how many device-sensor pairs, and the PASS / WARN /
NO DATA / ERROR counts), plus a one-way hash of the submitter's token so repeat
senders can be recognised. Never the token, and never the readings.

### Anywhere else

```bash
./start.sh        # serves on $PORT, default 7777
```

`start.sh` creates `.venv` and installs Python dependencies, rebuilds the
frontend when anything in `frontend/` is newer than the last build, and runs
gunicorn with a 300 s timeout (large reports take minutes). The built frontend
is not committed, so a deploy always serves the current source. Needs Python
3.12+ and Node 20+ on the host.

## Develop

```bash
BEARER_TOKEN="Bearer <jwt>" ./start.sh             # API + built UI on 7777
cd frontend && npm run dev                         # hot-reload UI, proxies /api to 7777
cd backend && ../.venv/bin/python -m unittest discover tests
```

`BEARER_TOKEN` is for local development only. In Launchpad, the app is opened
with `?token=<sso>`; the frontend exchanges it through `POST /api/auth/sso` and
sends the signed-in user's own token on every request.

## How it works

| Piece | File |
|---|---|
| Calculations (pure functions) | `backend/compute.py` |
| Formula registry: labels, formulas, ledger columns, evaluators | `backend/formulas.py` |
| One validation run: targets × shift windows, parallel fetches | `backend/validation.py` |
| IOsense connector client (read-only) | `backend/iosense.py` |
| Excel export (Summary, Ledger, Method sheets) | `backend/report.py` |
| API + static frontend | `backend/app.py` |
| UI | `frontend/src/` |

### Adding a calculation

Formulas live in `backend/formulas.json`: label, formula, ledger columns and the
parameters they need. The UI renders whatever is declared there, so a formula
that reuses an existing `compute` kind (`delta`, `threshold_time`, `mean`,
`time_weighted_mean`, `availability`, `load_factor`) is a JSON edit only. A new
kind also needs one evaluator function in `formulas.py`.

| Formula | Formula |
|---|---|
| Energy Consumption | Δ = (Last DP − First DP) × m |
| Run-Hours | Σ time intervals where reading ≥ threshold |
| Average Value | Σ readings ÷ N |
| Time-Weighted Average | Σ(reading × interval) ÷ Σ interval |
| OEE Availability | (Run-Hours ÷ Planned Hours) × 100 |
| Load Factor | (Average ÷ Peak) × 100 |

Specific Energy Consumption is registered but unavailable: it needs a
production-output source Newton cannot select yet.

### Rules every report follows

- **Raw readings, calibration applied by Newton.** Data comes from
  `getDataCalibration/.../false`; the ledger shows the `m`, `c` and factor used
  and whether they came from device config or a manual override.
- **Shift windows are `[start, end)`** in `SITE_TIMEZONE` (default
  `Asia/Kolkata`). A reading stamped exactly at the end belongs to the next shift.
- **Missing data is `NO DATA`, never zero.** Platform failures are `ERROR`.
- **Gap tolerance** (default 15 min): if a device stops reporting, its last
  reading is trusted for this long. Longer silences are unknown time, counted
  as neither running nor stopped, and the shift is flagged.
- **Output unit** converts within a unit family (Wh→kWh, A→mA, h→min).
  Thresholds are always given in the sensor's own unit.

## Validation log

Checked against the platform through the MCP connector on 15 Sep 2026, device
EVOEM_C1 (Energymeter, `m=1`, `c=0`), shift 14 Sep 07:00 – 15 Sep 07:00 IST.
Raw readings are saved in `backend/tests/fixtures/`.

- **Energy (D30):** Newton's last − first is **1,268.00 kWh**, matching the
  platform's `consumption/getOperationDataWithTime` first/last points exactly.
  Treating the window end as inclusive gives 1,268.25: the extra 0.25 is the
  next shift's first reading, stamped exactly 07:00:00.
- **Reporting interval** on this meter is ~70 s (1,245 readings/day), not 30 s.
- **Run-hours (D6, threshold 3 A):** Newton computes 7.15 h running,
  16.84 h stopped. The platform's `deviceData` compressor run-time route:
  - with epoch **milliseconds** returns `count: 0`, success, stamped with the
    current time — a silent wrong answer;
  - with epoch **seconds** returns `count: 352`, which is exactly the number of
    readings **strictly above** 3 A. It is a reading count, not a duration.

  Newton therefore does not use that route.

## Open items

- Validate `calibration=false` on a sensor with `m ≠ 1` (every sensor checked
  on this account had `m=1`).
- Phase 2 (clusters, dashboards/widgets) needs a connector with the
  `devices-clusters` category; the current read-only connector cannot see it.
- Device activity status ("Live") is not shown yet; its status codes are
  undocumented.
