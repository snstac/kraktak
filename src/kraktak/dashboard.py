#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright Sensors & Signals LLC https://www.snstac.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Optional KrakTAK status & control dashboard (standalone aiohttp app).

Run with::

    kraktak-dashboard -c kraktak.conf

It shows the live KrakenSDR settings and latest DOA, and exposes manual control
buttons that drive the same :class:`~kraktak.control.KrakenController` backends
used by the TAK control plane.
"""

import argparse
import configparser
import os

from aiohttp import web

import kraktak
from kraktak.classes import parse_doa_csv
from kraktak.control import BACKENDS, AUTO_ORDER, control_host, validate

INDEX_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KrakTAK</title>
<style>
 body{background:#111;color:#ffd400;font-family:system-ui,Arial,sans-serif;margin:0;padding:1.5rem}
 h1{margin:0 0 1rem;font-size:1.6rem}
 .card{background:#1b1b1b;border:1px solid #333;border-radius:8px;padding:1rem;margin-bottom:1rem}
 label{display:block;margin:.5rem 0 .2rem;color:#ccc}
 input,button{padding:.5rem;border-radius:6px;border:1px solid #444;background:#222;color:#fff}
 button{cursor:pointer;background:#2a6;color:#012;border:0;font-weight:600}
 pre{white-space:pre-wrap;word-break:break-all;color:#9f9}
 .row{display:flex;gap:.5rem;flex-wrap:wrap;align-items:end}
 .msg{color:#8cf;min-height:1.2em}
</style></head><body>
<h1>KrakTAK &mdash; KrakenSDR &rarr; TAK</h1>
<div class="card"><h2>Status</h2><pre id="status">loading...</pre></div>
<div class="card"><h2>Control</h2>
 <div class="row">
  <div><label>Frequency (MHz)</label><input id="freq" type="number" step="0.0001"></div>
  <button onclick="ctl('set_frequency',{freq:+freq.value})">Tune</button>
 </div>
 <div class="row">
  <div><label>Gain (dB)</label><input id="gain" type="number" step="0.1"></div>
  <button onclick="ctl('set_gain',{gain:+gain.value})">Set Gain</button>
 </div>
 <div class="row">
  <div><label>Latitude</label><input id="lat" type="number" step="any"></div>
  <div><label>Longitude</label><input id="lon" type="number" step="any"></div>
  <button onclick="ctl('set_coordinates',{latitude:+lat.value,longitude:+lon.value})">Set Coords</button>
 </div>
 <p class="msg" id="msg"></p>
</div>
<script>
async function refresh(){
 try{const r=await fetch('api/status');const j=await r.json();
  document.getElementById('status').textContent=JSON.stringify(j,null,2);}
 catch(e){document.getElementById('status').textContent='error: '+e;}
}
async function ctl(action,args){
 document.getElementById('msg').textContent='...';
 const r=await fetch('api/control',{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({action,args})});
 const j=await r.json();
 document.getElementById('msg').textContent=j.ok?('OK: '+action):(j.error||'error');
 refresh();
}
refresh();setInterval(refresh,5000);
</script></body></html>"""


async def _controller(app):
    host = control_host(app["config"])
    backend = (app["config"].get("CONTROL_BACKEND")
               or kraktak.DEFAULT_CONTROL_BACKEND).lower()
    session = app["session"]
    if backend != "auto" and backend in BACKENDS:
        return BACKENDS[backend](host, session, app["config"])
    for name in AUTO_ORDER:
        ctrl = BACKENDS[name](host, session, app["config"])
        if await ctrl.available():
            return ctrl
    return None


async def handle_index(_request):
    return web.Response(text=INDEX_HTML, content_type="text/html")


async def handle_status(request):
    app = request.app
    config = app["config"]
    out = {"settings": None, "doa": None}
    ctrl = await _controller(app)
    if ctrl is not None:
        try:
            out["settings"] = await ctrl.get_config()
        except Exception as exc:  # noqa: BLE001
            out["settings_error"] = str(exc)

    feed = config.get("FEED_URL") or kraktak.DEFAULT_FEED_URL
    try:
        async with app["session"].get(feed) as resp:
            text = await resp.text()
        doa = parse_doa_csv(text.splitlines()[0]) if text.strip() else None
        if doa:
            out["doa"] = {
                "station": doa.station, "frequency": doa.frequency,
                "max_doa_angle": doa.max_doa_angle, "confidence": doa.confidence,
                "rssi": doa.rssi,
            }
    except Exception as exc:  # noqa: BLE001
        out["doa_error"] = str(exc)
    return web.json_response(out)


async def handle_control(request):
    app = request.app
    try:
        body = await request.json()
        action = body["action"]
        args = body.get("args", {})
    except Exception as exc:  # noqa: BLE001
        return web.json_response({"ok": False, "error": f"bad request: {exc}"})

    err = validate(action, args)
    if err:
        return web.json_response({"ok": False, "error": err})

    ctrl = await _controller(app)
    if ctrl is None:
        return web.json_response({"ok": False, "error": "no control backend"})
    try:
        await getattr(ctrl, action)(**args)
    except Exception as exc:  # noqa: BLE001
        return web.json_response({"ok": False, "error": str(exc)})
    return web.json_response({"ok": True})


def build_app(config) -> web.Application:
    app = web.Application()
    app["config"] = config

    async def _on_start(a):
        import aiohttp
        a["session"] = aiohttp.ClientSession()

    async def _on_clean(a):
        await a["session"].close()

    app.on_startup.append(_on_start)
    app.on_cleanup.append(_on_clean)
    app.add_routes([
        web.get("/", handle_index),
        web.get("/api/status", handle_status),
        web.post("/api/control", handle_control),
    ])
    return app


def _load_config(path):
    section = {}
    if path and os.path.exists(path):
        cp = configparser.ConfigParser()
        cp.read(path)
        if cp.has_section("kraktak"):
            section = dict(cp["kraktak"])
    # Environment overrides file.
    for key in ("FEED_URL", "KRAKEN_HOST", "CONTROL_BACKEND", "API_AGENT_PORT",
                "MIDDLEWARE_PORT", "DSP_PORT", "DASHBOARD_HOST", "DASHBOARD_PORT"):
        if os.getenv(key):
            section[key] = os.getenv(key)
    return section


def main() -> None:
    parser = argparse.ArgumentParser(description="KrakTAK status & control dashboard")
    parser.add_argument("-c", "--config", default=os.getenv("CONFIG", ""))
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    config = _load_config(args.config)
    host = args.host or config.get("DASHBOARD_HOST", "0.0.0.0")
    port = args.port or int(config.get("DASHBOARD_PORT", "8000"))
    web.run_app(build_app(config), host=host, port=port)


if __name__ == "__main__":
    main()
