#!/usr/bin/env bash
# Start Newton: install dependencies, rebuild the frontend when its source is
# newer than the build, then serve API + UI on $PORT (default 7777).
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PORT:-7777}"

if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install --quiet --disable-pip-version-check -r requirements.txt

build_stamp=frontend/dist/index.html
if [ ! -f "$build_stamp" ] || [ -n "$(find frontend/src frontend/index.html frontend/package.json \
    frontend/package-lock.json frontend/vite.config.js -newer "$build_stamp" -print -quit)" ]; then
  echo "Building frontend…"
  (cd frontend && npm ci --no-audit --no-fund && npm run build)
fi

# A large report (31 days x 20 device-sensor pairs) makes ~620 platform fetches
# and can take a few minutes, well past gunicorn's default 30 s worker timeout.
exec .venv/bin/gunicorn --chdir backend --bind "0.0.0.0:${PORT}" \
  --workers 2 --threads 4 --timeout 300 --access-logfile - app:app
