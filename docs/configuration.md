# Configuration

KrakTAK reads settings from an INI config file (`-c kraktak.conf`, section
`[kraktak]`) or from environment variables of the same name. Environment
variables override the file, which is convenient for Docker and systemd.

See [`kraktak-example.conf`](https://github.com/snstac/kraktak/blob/main/kraktak-example.conf)
for a complete, commented template.

## Core

| Setting | Description | Default |
| --- | --- | --- |
| `COT_URL` | TAK destination: `tcp://host:8087`, `tls://host:8089`, or `udp://239.2.3.1:6969` | - |
| `FEED_URL` | KrakenSDR DOA CSV export | `http://krakensdr:8081/DOA_value.html` |
| `POLL_INTERVAL` | DOA poll interval, seconds | `3` |
| `COT_STALE` | CoT stale time, seconds | `120` |

`COT_URL` also honors the standard PyTAK TLS variables (`PYTAK_TLS_CLIENT_CERT`,
etc.) for connecting to a TAK Server.

## CoT rendering

| Setting | Description | Default |
| --- | --- | --- |
| `COT_TYPES` | Comma list of `sensor`, `bearing_line`, `range_bearing`, `lob`, `cep`, `spi`, `target_range_bearing`, `spot_poi` | `lob,bearing_line,spi,target_range_bearing` |
| `LOB_LENGTH_M` | Bearing-line length, meters (`LOB_LENGTH_KM` also accepted). Default assumed range for `spi` / `target_range_bearing`. | `10000` |
| `TARGET_FIX_RANGE_M` | Optional override for assumed emitter range used by `spi` / `target_range_bearing` | same as `LOB_LENGTH_M` |
| `PERSIST_LOB` | Randomize LOB UID so bearings leave a trail | `false` |
| `CEP_MIN_RADIUS_M` / `CEP_MAX_RADIUS_M` | `cep` ellipse size bounds | `100` / `2000` |

## Filtering

| Setting | Description |
| --- | --- |
| `MIN_CONFIDENCE` | Drop detections below this confidence (0-99) |
| `MIN_RSSI` | Drop detections below this RSSI (dB) |
| `DOA_IGNORE_START` / `DOA_IGNORE_END` | Drop bearings inside this compass wedge |

## Control plane (TAK -> KrakenSDR)

| Setting | Description | Default |
| --- | --- | --- |
| `ENABLE_CONTROL` | Accept control commands from TAK | `false` |
| `CONTROL_BACKEND` | `auto`, `api_agent`, `middleware`, or `settings_json` | `auto` |
| `KRAKEN_HOST` | Control host (defaults to the `FEED_URL` host) | - |
| `API_AGENT_PORT` | kraken_api_agent port | `8181` |
| `MIDDLEWARE_PORT` | krakensdr_doa middleware port | `8042` |
| `DSP_PORT` | settings.json / upload port | `8081` |

## Dashboard

| Setting | Description | Default |
| --- | --- | --- |
| `DASHBOARD_HOST` | Bind address for `kraktak-dashboard` | `0.0.0.0` |
| `DASHBOARD_PORT` | Bind port for `kraktak-dashboard` | `8000` |
