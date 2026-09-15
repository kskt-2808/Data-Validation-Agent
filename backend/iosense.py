"""Read-only IOsense connector client.

The signed-in Launchpad user's own token is forwarded on every request, so the
app sees exactly the devices that user can see. Never logs the token.
"""
from __future__ import annotations

import os
import time
from datetime import datetime
from urllib.parse import quote

import requests

BASE = os.environ.get("IOSENSE_BASE_URL", "https://connector.iosense.io").rstrip("/")
ORGANISATION = os.environ.get("IOSENSE_ORGANISATION", "https://iosense.io")

# FSV answers many failures as HTTP 200 + success:false, and some of those clear
# on a byte-identical retry. Errors naming access or ownership never do.
RETRY_DELAYS_S = (0.5, 1.5, 3.0)
PERMANENT_ERRORS = ("access denied", "permission", "not added", "not found")
AUTH_ERRORS = ("authentication required", "session expired")


class AuthError(Exception):
    """The token is missing, invalid or expired."""


class UpstreamError(Exception):
    """The platform did not return a usable answer. Report as unknown, never as zero."""


def exchange_sso_token(sso_token: str) -> str:
    """Swap Launchpad's one-time ?token= for a 'Bearer <jwt>' session token."""
    try:
        res = requests.get(f"{BASE}/api/retrieve-sso-token/{quote(sso_token, safe='')}",
                           headers={"organisation": ORGANISATION, "ngsw-bypass": "true"},
                           timeout=20)
        body = res.json()
    except (requests.RequestException, ValueError) as err:
        raise UpstreamError(f"SSO exchange failed: {err}") from None
    if not body.get("success") or not body.get("token"):
        raise AuthError("Launchpad sign-in token was rejected or has expired. "
                        "Reopen Newton from Launchpad.")
    return body["token"]


class Client:
    def __init__(self, token: str):
        token = token.strip()
        self.token = token if token.lower().startswith("bearer ") else f"Bearer {token}"

    def _call(self, method: str, path: str, body: dict | None = None, timeout: int = 60) -> dict:
        headers = {"Authorization": self.token, "Content-Type": "application/json",
                   "organisation": ORGANISATION, "ngsw-bypass": "true"}
        last = ""
        for attempt in range(len(RETRY_DELAYS_S) + 1):
            if attempt:
                time.sleep(RETRY_DELAYS_S[attempt - 1])
            try:
                res = requests.request(method, BASE + path, json=body, headers=headers,
                                       timeout=timeout)
            except requests.RequestException as err:
                last = str(err)
                continue
            if res.status_code in (401, 403):
                raise AuthError("IOsense rejected the session token. Reopen Newton from Launchpad.")
            if res.status_code >= 500:
                last = f"HTTP {res.status_code}"
                continue
            try:
                payload = res.json()
            except ValueError:
                last = f"HTTP {res.status_code} with a non-JSON body"
                continue
            if isinstance(payload, dict) and payload.get("success"):
                return payload
            last = str(payload.get("errors") if isinstance(payload, dict) else payload)[:300]
            if any(e in last.lower() for e in AUTH_ERRORS):
                raise AuthError(last)
            if any(e in last.lower() for e in PERMANENT_ERRORS):
                raise UpstreamError(last)
        raise UpstreamError(f"{method} {path.split('/')[3] if path.count('/') > 3 else path} "
                            f"failed after {len(RETRY_DELAYS_S) + 1} attempts: {last}")

    def list_devices(self, page_size: int = 50) -> list[dict]:
        """Every device on the account, trimmed to what the UI and calculations need."""
        devices, page = [], 1
        while True:
            payload = self._call("PUT", f"/api/account/devices/{page}/{page_size}",
                                 {"search": {}, "sort": "AtoZ"})
            data = payload.get("data") or {}
            batch = data.get("data") or []
            devices.extend(batch)
            if not batch or len(devices) >= (data.get("totalCount") or 0):
                break
            page += 1
        return [_summarize_device(d) for d in devices if d.get("devID")]

    def raw_series(self, dev_id: str, sensor: str, start_ms: int, end_ms: int) -> list[tuple[int, object]]:
        """Uncalibrated readings for one sensor. Newton applies m and c itself.

        getDataCalibration with calibration 'false' returns stored values; the
        same route with 'true' would apply m/c server-side, and applying it
        again here would double-calibrate.
        """
        path = (f"/api/account/deviceData/getDataCalibration/{quote(dev_id, safe='')}/"
                f"{quote(sensor, safe='')}/{start_ms}/{end_ms}/false")
        data = self._call("GET", path).get("data") or []
        series = data[0] if data and isinstance(data[0], list) else data
        return [(_epoch_ms(p["time"]), p.get("value")) for p in series
                if isinstance(p, dict) and p.get("time")]


def _epoch_ms(iso: str) -> int:
    return round(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)


def _number(value, default: float) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _summarize_device(device: dict) -> dict:
    params = device.get("params") or {}
    units = device.get("unitSelected") or {}
    sensors = []
    for s in device.get("sensors") or []:
        sid = s.get("sensorId")
        if not sid:
            continue
        p = {x.get("paramName"): x.get("paramValue") for x in params.get(sid) or []}
        sensors.append({
            "id": sid,
            "name": (s.get("sensorName") or sid).strip(),
            "unit": units.get(sid) or "",
            "m": _number(p.get("m"), 1.0),
            "c": _number(p.get("c"), 0.0),
        })
    return {
        "devID": device["devID"],
        "devName": device.get("devName") or device["devID"],
        "devType": device.get("devTypeName") or "",
        "sensors": sensors,
    }
