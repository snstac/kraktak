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

"""KrakTAK status & control dashboard (multi-Kraken, runtime config, telemetry)."""

from __future__ import annotations

import argparse
import configparser
import os
from typing import Any, Dict, List

from aiohttp import web

import kraktak
from kraktak.classes import parse_doa_csv
from kraktak.config_loader import (
    KrakenServerConfig,
    load_kraken_servers,
    load_runtime_document,
    runtime_path_from_config,
    save_runtime_document,
)
from kraktak.control import BACKENDS, AUTO_ORDER, control_host, validate
from kraktak.telemetry import STORE

INDEX_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KrakTAK</title>
<style>
 body{background:#0f0f0f;color:#e8e8e8;font-family:system-ui,sans-serif;margin:0;padding:1rem 1.5rem 3rem}
 h1{color:#ffd400;margin:0 0 .25rem;font-size:1.5rem}
 .sub{color:#888;margin:0 0 1.25rem;font-size:.9rem}
 .grid{display:grid;gap:1rem;grid-template-columns:repeat(auto-fit,minmax(280px,1fr))}
 .card{background:#1a1a1a;border:1px solid #333;border-radius:8px;padding:1rem}
 h2{margin:0 0 .75rem;font-size:1rem;color:#ffd400}
 label{display:block;margin:.4rem 0 .15rem;font-size:.85rem;color:#aaa}
 input,select,textarea{width:100%;box-sizing:border-box;padding:.45rem;border-radius:6px;border:1px solid #444;background:#222;color:#fff}
 textarea{font-family:ui-monospace,monospace;font-size:.8rem;min-height:6rem}
 button{padding:.5rem .9rem;border-radius:6px;border:0;cursor:pointer;font-weight:600;background:#2a8f4a;color:#fff;margin-top:.5rem}
 button.secondary{background:#444}
 .row{display:flex;gap:.5rem;flex-wrap:wrap;align-items:end}
 .row>*{flex:1;min-width:120px}
 .pill{display:inline-block;padding:.15rem .5rem;border-radius:4px;font-size:.75rem}
 .ok{background:#163a24;color:#6f6}.bad{background:#3a1616;color:#f88}
 table{width:100%;border-collapse:collapse;font-size:.85rem}
 th,td{text-align:left;padding:.35rem;border-bottom:1px solid #333}
 .msg{color:#8cf;min-height:1.2em;margin-top:.5rem}
 .note{font-size:.8rem;color:#888;margin-top:.5rem}
</style></head><body>
<h1>KrakTAK</h1>
<p class="sub">KrakenSDR &rarr; TAK &mdash; multi-server ops dashboard</p>
<div class="grid">
 <div class="card"><h2>Telemetry</h2>
  <p>Packets: <strong id="pkts">0</strong> &middot; Last CoT: <strong id="ago">—</strong>s ago</p>
  <table><thead><tr><th>Feed</th><th>Status</th><th>DOA</th><th>Conf</th></tr></thead>
  <tbody id="servers"></tbody></table>
 </div>
 <div class="card"><h2>TAK (read-only)</h2>
  <p class="note">Change COT_URL in kraktak.conf and restart the bridge.</p>
  <label>COT_URL</label><input id="cot_url" readonly>
  <label>Multicast mirror</label><input id="mcast" readonly>
 </div>
</div>
<div class="card" style="margin-top:1rem"><h2>Kraken servers</h2>
 <p class="note">Saved to runtime JSON; the bridge reloads each poll cycle.</p>
 <textarea id="servers_json"></textarea>
 <div class="row">
  <div><label>Poll interval (s)</label><input id="poll_interval" type="number" min="1"></div>
  <div><label>Multicast mirror</label>
   <select id="enable_mcast"><option value="false">off</option><option value="true">on</option></select>
  </div>
 </div>
 <div class="row">
  <div><label>DOA wedge start (&deg;)</label><input id="wedge_start" type="number"></div>
  <div><label>DOA wedge end (&deg;)</label><input id="wedge_end" type="number"></div>
 </div>
 <button onclick="saveConfig()">Save runtime config</button>
 <p class="msg" id="cfg_msg"></p>
</div>
<div class="card" style="margin-top:1rem"><h2>Control (primary Kraken)</h2>
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
 <p class="msg" id="ctl_msg"></p>
</div>
<script>
let runtimeDoc={};
async function refresh(){
 try{
  const r=await fetch('/api/status');const j=await r.json();
  document.getElementById('pkts').textContent=j.telemetry?.packets_sent??0;
  document.getElementById('ago').textContent=j.telemetry?.last_packet_ago??'—';
  const tb=document.getElementById('servers');tb.innerHTML='';
  const rows=j.servers||[];
  if(!rows.length){tb.innerHTML='<tr><td colspan="4">No servers</td></tr>';}
  rows.forEach(s=>{
   const tr=document.createElement('tr');
   const st=s.reachable?'<span class="pill ok">up</span>':'<span class="pill bad">down</span>';
   tr.innerHTML=`<td title="${s.feed_url}">${s.station||s.feed_url}</td><td>${st}</td>
    <td>${s.doa??'—'}°</td><td>${s.confidence??'—'}</td>`;
   tb.appendChild(tr);
  });
  if(j.tak){document.getElementById('cot_url').value=j.tak.cot_url||'';
   document.getElementById('mcast').value=j.tak.multicast||'';}
 }catch(e){console.error(e);}
}
async function loadConfig(){
 try{
  const r=await fetch('/api/config');const j=await r.json();
  runtimeDoc=j.runtime||{};
  document.getElementById('servers_json').value=JSON.stringify(runtimeDoc.kraken_servers||j.servers||[],null,2);
  document.getElementById('poll_interval').value=runtimeDoc.poll_interval||j.poll_interval||3;
  document.getElementById('enable_mcast').value=String(runtimeDoc.enable_multicast_mirror??false);
  document.getElementById('wedge_start').value=runtimeDoc.doa_ignore_start??'';
  document.getElementById('wedge_end').value=runtimeDoc.doa_ignore_end??'';
 }catch(e){document.getElementById('cfg_msg').textContent='load error: '+e;}
}
async function saveConfig(){
 let servers;try{servers=JSON.parse(document.getElementById('servers_json').value);}catch(e){
  document.getElementById('cfg_msg').textContent='Invalid JSON: '+e;return;}
 const body={
  kraken_servers:servers,
  poll_interval:+document.getElementById('poll_interval').value||3,
  enable_multicast_mirror:document.getElementById('enable_mcast').value==='true',
  doa_ignore_start:document.getElementById('wedge_start').value||null,
  doa_ignore_end:document.getElementById('wedge_end').value||null
 };
 const r=await fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const j=await r.json();
 document.getElementById('cfg_msg').textContent=j.ok?'Saved.':'Error: '+(j.error||'unknown');
 refresh();
}
async function ctl(action,args){
 document.getElementById('ctl_msg').textContent='...';
 const r=await fetch('/api/control',{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({action,args})});
 const j=await r.json();
 document.getElementById('ctl_msg').textContent=j.ok?('OK: '+action):(j.error||'error');
}
loadConfig();refresh();setInterval(refresh,5000);
</script></body></html>"""


def _runtime_path(config: dict) -> str:
    return runtime_path_from_config(config)


def _default_runtime_document(config: dict) -> Dict[str, Any]:
    servers = load_kraken_servers(config, _runtime_path(config))
    return {
        "kraken_servers": [s.as_dict() for s in servers],
        "poll_interval": int(config.get("POLL_INTERVAL", kraktak.DEFAULT_POLL_INTERVAL)),
        "enable_multicast_mirror": str(
            config.get("ENABLE_MULTICAST_MIRROR", kraktak.DEFAULT_ENABLE_MULTICAST)
        ).lower() in ("1", "true", "yes"),
        "doa_ignore_start": config.get("DOA_IGNORE_START") or None,
        "doa_ignore_end": config.get("DOA_IGNORE_END") or None,
    }


async def _controller(app):
    host = control_host(app["config"])
    backend = (
        app["config"].get("CONTROL_BACKEND") or kraktak.DEFAULT_CONTROL_BACKEND
    ).lower()
    session = app["session"]
    if backend != "auto" and backend in BACKENDS:
        return BACKENDS[backend](host, session, app["config"])
    for name in AUTO_ORDER:
        ctrl = BACKENDS[name](host, session, app["config"])
        if await ctrl.available():
            return ctrl
    return None


async def _poll_server_live(
    session, server: KrakenServerConfig
) -> Dict[str, Any]:
    """Poll one feed when the main bridge is not sharing telemetry."""
    out = server.as_dict()
    out["reachable"] = False
    try:
        async with session.get(server.feed_url, timeout=10) as resp:
            if resp.status != 200:
                out["last_error"] = f"HTTP {resp.status}"
                return out
            text = await resp.text()
        out["reachable"] = True
        if text.strip():
            doa = parse_doa_csv(text.splitlines()[0])
            if doa:
                out["station"] = doa.station or out.get("station")
                out["doa"] = doa.max_doa_angle
                out["confidence"] = doa.confidence
                out["rssi"] = doa.rssi
                out["lat"] = doa.latitude
                out["lon"] = doa.longitude
    except Exception as exc:  # noqa: BLE001
        out["last_error"] = str(exc)
    return out


async def handle_index(_request):
    return web.Response(text=INDEX_HTML, content_type="text/html")


async def handle_status(request):
    app = request.app
    config = app["config"]
    telemetry = STORE.snapshot()
    servers_out: List[Dict[str, Any]] = telemetry.get("servers") or []

    if not servers_out:
        servers = load_kraken_servers(config, _runtime_path(config))
        for server in servers:
            servers_out.append(await _poll_server_live(app["session"], server))

    tak = {
        "cot_url": config.get("COT_URL", ""),
        "multicast": config.get("COT_MULTICAST_URL")
        or kraktak.DEFAULT_COT_MULTICAST_URL,
        "enable_multicast_mirror": config.get(
            "ENABLE_MULTICAST_MIRROR", kraktak.DEFAULT_ENABLE_MULTICAST
        ),
    }

    out: Dict[str, Any] = {
        "telemetry": telemetry,
        "servers": servers_out,
        "tak": tak,
        "runtime_path": _runtime_path(config),
    }

    ctrl = await _controller(app)
    if ctrl is not None:
        try:
            out["settings"] = await ctrl.get_config()
        except Exception as exc:  # noqa: BLE001
            out["settings_error"] = str(exc)

    return web.json_response(out)


async def handle_config_get(request):
    app = request.app
    config = app["config"]
    path = _runtime_path(config)
    runtime = load_runtime_document(path)
    if not runtime.get("kraken_servers"):
        runtime = _default_runtime_document(config)
    return web.json_response(
        {
            "runtime": runtime,
            "runtime_path": path,
            "servers": [
                s.as_dict() for s in load_kraken_servers(config, path)
            ],
            "poll_interval": config.get("POLL_INTERVAL", kraktak.DEFAULT_POLL_INTERVAL),
        }
    )


async def handle_config_post(request):
    app = request.app
    config = app["config"]
    path = _runtime_path(config)
    try:
        body = await request.json()
    except Exception as exc:  # noqa: BLE001
        return web.json_response({"ok": False, "error": f"bad JSON: {exc}"})

    servers = body.get("kraken_servers")
    if servers is not None:
        validated = []
        for entry in servers:
            try:
                validated.append(KrakenServerConfig.from_dict(entry).as_dict())
            except ValueError as exc:
                return web.json_response({"ok": False, "error": str(exc)})
        body["kraken_servers"] = validated

    existing = load_runtime_document(path)
    existing.update(body)
    try:
        save_runtime_document(path, existing)
    except OSError as exc:
        return web.json_response({"ok": False, "error": str(exc)})
    return web.json_response({"ok": True, "runtime_path": path})


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
    app.add_routes(
        [
            web.get("/", handle_index),
            web.get("/api/status", handle_status),
            web.get("/api/config", handle_config_get),
            web.post("/api/config", handle_config_post),
            web.post("/api/control", handle_control),
        ]
    )
    return app


def _load_config(path):
    section = {}
    if path and os.path.exists(path):
        cp = configparser.ConfigParser()
        cp.read(path)
        if cp.has_section("kraktak"):
            section = dict(cp["kraktak"])
    for key in (
        "FEED_URL",
        "KRAKEN_HOST",
        "KRAKEN_SERVERS",
        "RUNTIME_CONFIG",
        "COT_URL",
        "COT_MULTICAST_URL",
        "ENABLE_MULTICAST_MIRROR",
        "CONTROL_BACKEND",
        "API_AGENT_PORT",
        "MIDDLEWARE_PORT",
        "DSP_PORT",
        "DASHBOARD_HOST",
        "DASHBOARD_PORT",
        "POLL_INTERVAL",
        "DOA_IGNORE_START",
        "DOA_IGNORE_END",
    ):
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
