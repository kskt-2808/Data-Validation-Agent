# Newton — Data Validation Agent

A Launchpad app that recomputes device figures from raw iosense readings and
exports an auditable Excel report. Phase 1 covers devices: day-wise energy
consumption, run-hours and time-weighted averages, per shift.

## Deploy

Start command (AI Studio Manager, systemd, or by hand):

```bash
./start.sh        # serves on port 7777; override with PORT=...
```

`start.sh` creates `.venv` and installs Python dependencies, rebuilds the
frontend when anything in `frontend/` is newer than the last build, and runs
gunicorn with a 300 s timeout (large reports take minutes). The built frontend
is not committed, so a deploy always serves the current source. Needs Python
3.12+ and Node 20+ on the host.

Register `http://<host>:7777/` as the application URL in Launchpad.

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
| Recipe registry: labels, formulas, ledger columns, evaluators | `backend/recipes.py` |
| One validation run: targets × shift windows, parallel fetches | `backend/validation.py` |
| IOsense connector client (read-only) | `backend/iosense.py` |
| Excel export (Summary, Ledger, Method sheets) | `backend/report.py` |
| API + static frontend | `backend/app.py` |
| UI | `frontend/src/` |

To add a calculation, add an entry to `RECIPES` and an evaluator to
`EVALUATORS` in `recipes.py`. The UI reads both from `/api/recipes`.

### Rules every report follows

- **Raw readings, calibration applied by Newton.** Data comes from
  `getDataCalibration/.../false`; the ledger shows the `m`, `c` and factor used
  and whether they came from device config or a manual override.
- **Shift windows are `[start, end)`** in `SITE_TIMEZONE` (default
  `Asia/Kolkata`). A reading stamped exactly at the end belongs to the next shift.
- **Missing data is `NO DATA`, never zero.** Platform failures are `ERROR`.
- **Max gap** (default 15 min): a reading holds for at most this long. Longer
  silences are unknown time, counted as neither running nor stopped.

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
