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

### Settings in AI Studio Manager

Its **Env Config** button writes the variables you enter to a `.env` file at the
repository root; its pm2 config passes only `PORT` and `NODE_ENV`. Newton reads
that file at startup (`backend/dotenv_loader.py`), so UI settings take effect on
the next **Update Deployment**. A real environment variable always wins over the
file.

### Feedback settings

The Results page collects a rating and a note. Each submission appends to a
JSON-lines file and, if a webhook is set, posts to Teams or Slack.

| Variable | Meaning |
|---|---|
| `FEEDBACK_FILE` | Where to append. Default `~/newton-feedback/feedback.jsonl` — outside the repo, so a redeploy cannot erase it. |
| `FEEDBACK_WEBHOOK_URL` | Teams Workflow URL, Slack webhook, or a classic Teams connector. A failed post never loses the entry; the file is the record. |
| `FEEDBACK_WEBHOOK_FORMAT` | `card` or `text`. By default the URL decides: Teams Workflows (Power Automate) need an Adaptive Card, Slack and classic connectors take plain text. |
| `FEEDBACK_ADMIN_KEY` | Enables `GET /api/feedback/export.csv?key=…`. Unset means the export returns 404. |
| `CUSTOM_FORMULAS_FILE` | Where user-written formulas are stored. Default `~/newton-formulas/custom.json`, outside the repo for the same reason. |

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

### Adding a formula

Formulas live in `backend/formulas.json`. The UI renders whatever is declared
there, so a formula that reuses an existing `compute` kind needs **no code** —
add an entry, push, Update deployment.

Compute kinds available today:

| kind | what it does | used by |
|---|---|---|
| `delta` | last reading − first reading, × m | energy or water totalisers |
| `threshold_time` | time at or above a per-device threshold | run-hours |
| `mean` | Σ readings ÷ N | average current, PF |
| `time_weighted_mean` | Σ(reading × interval) ÷ Σ interval | uneven reporting |
| `integrate` | Σ(rate × interval) | volume from a flow rate |
| `availability` | run-hours ÷ planned hours × 100 | OEE |
| `load_factor` | average ÷ peak × 100 | demand |

A minimal entry — water totaliser, reusing `delta`:

```json
{
  "id": "water_consumption",
  "group": "Water",
  "label": "Water Consumption (Last DP − First DP)",
  "compute": "delta",
  "available": true,
  "expression": "Δ = (Last DP − First DP) × m",
  "method": "Last valid reading of the shift minus the first, times m. Readings below 0 are dropped as the meter's no-reading sentinel.",
  "aggregate": "sum",
  "unit": {"source": "sensor", "convertible": true},
  "labels": {"total": "Total water", "avg": "Average per shift", "peak": "Peak shift"},
  "columns": [
    {"key": "first_value", "label": "First Point (DP1)", "type": "number", "timeKey": "first_time"},
    {"key": "last_value", "label": "Last Point (DP2)", "type": "number", "timeKey": "last_time"},
    {"key": "raw_delta", "label": "Raw Delta", "type": "number"},
    {"key": "factor", "label": "Factor", "type": "factor"},
    {"key": "value", "label": "Computed Output", "type": "output"}
  ]
}
```

Fields: `unit.source` is `sensor`, `hours`, `percent` or `label` (named by the
operator); `aggregate` is `sum` or `mean`; `params` entries declare extra inputs
with `scope` `run` or `target`, `type` `number`, `text` or `unit`, and are
rendered by the UI automatically. Output unit and gap tolerance are added for
you where they apply.

A genuinely new calculation also needs one evaluator function in `formulas.py`
and an entry in `EVALUATORS` — `_integrate` is the shortest example.

### Custom formulas, written in the app

Users can write their own from the formula dropdown: a name, an expression, a
unit. They are stored server-side (`CUSTOM_FORMULAS_FILE`, default
`~/newton-formulas/custom.json`), appear in the dropdown for everyone, and only
their author can delete one.

The expression is arithmetic over values Newton computes for each shift —
`delta`, `mean`, `twa`, `min_reading`, `max_reading`, `coverage`, `shift_hours`,
`m`, `c`, plus `hours_above(x)`, `hours_below(x)`, `integral(basis)`, `abs`,
`round`. Calibration is already applied; `delta_raw` gives the meter's own
difference.

`backend/expressions.py` parses the expression to a syntax tree and allows only
numbers, those names and arithmetic. Attribute access, imports, comprehensions,
lambdas and unknown calls are refused before anything runs, so an expression
cannot reach the filesystem, the network or the interpreter. A shift missing a
value the expression needs is NO DATA, not zero.

Custom formulas are labelled **custom — not reviewed** in the UI and say so in
the Method sheet of every export, with the author and date. They have not been
through the tests the built-ins have, and a report should show that.

### Testing a formula

1. **Unit-test the maths** with numbers you can check by hand, in
   `backend/tests/test_compute.py`. `Integrate` is a short example: a rate of
   12 m³/h held for 30 minutes must total 6 m³.
2. **Test the whole run** in `backend/tests/test_validation.py` against the
   saved fixtures, so a formula is exercised end to end without the platform.
3. `cd backend && ../.venv/bin/python -m unittest discover tests`
4. **Check it against reality**: run it in the app on one device for one shift,
   and verify the ledger's DP1/DP2 and factor give the output by hand. The
   Method sheet of the Excel export states the rule that was applied.

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
