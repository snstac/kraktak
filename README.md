# KrakTAK: KrakenSDR to TAK

KrakTAK bridges a [KrakenSDR](https://www.krakenrf.com/) direction-finding
receiver to [TAK](https://tak.gov/) (ATAK / WinTAK / iTAK / TAK Server). It
polls the KrakenSDR DOA feed, renders each bearing as Cursor-on-Target (CoT),
and can be driven *back* from TAK to retune and reconfigure the radio.

Built on [PyTAK](https://github.com/snstac/pytak). CoT detail elements
(`__lob`, `__cep`, `signalInfo`) are validated against the MITRE/TAK CoT XSD
reference set.

## Features

- **DOA -> CoT** from the KrakenSDR "Kraken App" CSV export (`DOA_value.html`),
  including multi-VFO records.
- **Multiple renderings**, selectable via `COT_TYPES`:
  - `bearing_line` - a line of bearing (`u-d-f`) colored by azimuth
  - `lob` - a native TAK `__lob` detection (schema-valid `signalInfo` + `__startLocation`)
  - `range_bearing` - a TAK Range & Bearing line (`u-rb-a`)
  - `sensor` - the KrakenSDR station marker (`a-f-G-U-C`)
  - `cep` - a `__cep` error ellipse sized from detection confidence
- **Bi-directional control**: send commands from TAK (GeoChat or a
  `<__krakencmd>` detail) to retune frequency, set gain/VFO, or update station
  coordinates. Pluggable backends auto-detect the best available control path:
  - `api_agent` - [kraken_api_agent](https://github.com/ghostop14/kraken_api_agent) REST API (`:8181`)
  - `middleware` - krakensdr_doa middleware (`:8042`)
  - `settings_json` - portable `settings.json` upload (`:8081`)
- **Filtering**: confidence/RSSI thresholds and a DOA exclusion wedge.
- **Turn-key**: Debian/RPM packages, Docker image + Compose, and a systemd
  service.
- **Optional dashboard**: a lightweight status + manual-control web page.

## Install

### pip

```bash
pip install kraktak           # from PyPI
pip install -e .              # from a checkout
```

### Debian / Docker

```bash
# Debian package (built by CI / make package)
sudo apt install ./kraktak_*.deb

# Docker
docker build -f docker/Dockerfile -t kraktak:local .
docker compose -f docker/docker-compose.yml up --build
```

## Quick start

1. Copy `kraktak-example.conf` and edit `COT_URL` (your TAK destination) and
   `FEED_URL` (your KrakenSDR).
2. Run it:

```bash
kraktak -c kraktak.conf
```

Configuration may be supplied via the config file or environment variables of
the same name (handy for Docker/systemd). Key settings:

| Setting | Description | Default |
| --- | --- | --- |
| `COT_URL` | TAK destination (`tcp://`, `tls://`, `udp://`) | - |
| `FEED_URL` | Single KrakenSDR DOA CSV export | `http://krakensdr:8081/DOA_value.html` |
| `KRAKEN_SERVERS` | JSON array of feeds (multi-Kraken) | - |
| `RUNTIME_CONFIG` | Dashboard-saved JSON (hot reload) | `kraktak-runtime.json` |
| `POLL_INTERVAL` | DOA poll interval (s) | `3` |
| `ENABLE_MULTICAST_MIRROR` | Also send CoT to ATAK multicast | `false` |
| `ENABLE_GPSD` | Use gpsd when DOA has no position | `false` |
| `COT_TYPES` | Renderings: `sensor,bearing_line,range_bearing,lob,cep` | `bearing_line,lob` |
| `LOB_LENGTH_M` | Bearing-line length (m) | `10000` |
| `MIN_CONFIDENCE` / `MIN_RSSI` | Drop weak detections | unset |
| `DOA_IGNORE_START` / `DOA_IGNORE_END` | Exclusion wedge (deg) | unset |
| `ENABLE_CONTROL` | Accept control commands from TAK | `false` |
| `CONTROL_BACKEND` | `auto` / `api_agent` / `middleware` / `settings_json` | `auto` |

> Note: the bridge only transmits over `udp://` multicast. To receive control
> commands from TAK you must connect to a TAK Server over `tcp://`/`tls://`.

## Controlling the KrakenSDR from TAK

Enable `ENABLE_CONTROL = true` and send a GeoChat message (or a CoT carrying a
`<__krakencmd>` detail). The grammar:

```
kraken freq 462.5625      # tune center frequency (MHz)
kraken gain 16.6          # set uniform gain (dB)
kraken vfo 0 467000000    # set VFO-0 frequency (Hz)
kraken bw 0 12500         # set VFO-0 bandwidth (Hz)
kraken coord 34.70 -86.65 # set station coordinates
kraken status             # report current frequency/gain/station
```

KrakTAK replies with a GeoChat acknowledgement. For the most robust control,
install the API agent on the KrakenSDR:

```bash
# run ON the KrakenSDR device
bash extras/install_kraken_api_agent.sh
```

Otherwise KrakTAK falls back to uploading `settings.json` (it sets
`en_remote_control` on first push).

## Dashboard (optional)

```bash
kraktak-dashboard -c kraktak.conf   # serves on :8000 by default
```

Shows per-server status and telemetry, edits multi-Kraken runtime config
(poll interval, wedge filter, multicast mirror), and exposes tune/gain/coord
controls through the same backends as the TAK control plane.

## Development

```bash
make editable                 # pip install -e .
make install_test_requirements
make test                     # pytest (incl. XSD validation of __lob/__cep)
make lint flake8              # static checks
make package                  # build a Debian .deb
make rpm                      # build an RPM
```

## The snstac TAK sensor ecosystem

Different sensor, same workflow — pick the gateway for your application; most have a
matching Cockpit plugin for browser-based management:

| Application | Gateway | Cockpit plugin |
|---|---|---|
| Aircraft via ADS-B (1090 MHz / 978 MHz UAT) | [adsbcot](https://github.com/snstac/adsbcot) | [cockpit-adsbcot](https://github.com/snstac/cockpit-adsbcot) |
| Ships & vessels via AIS | [aiscot](https://github.com/snstac/aiscot) | [cockpit-aiscot](https://github.com/snstac/cockpit-aiscot), [cockpit-aiscatcher](https://github.com/snstac/cockpit-aiscatcher) |
| Drone / UAS Remote ID (counter-UAS) | [dronecot](https://github.com/snstac/dronecot) | [cockpit-dronecot](https://github.com/snstac/cockpit-dronecot) |
| Own position via GPS/GNSS | [lincot](https://github.com/snstac/lincot) | [cockpit-lincot](https://github.com/snstac/cockpit-lincot), [cockpit-gps](https://github.com/snstac/cockpit-gps) |
| Radio direction finding (KrakenSDR) | [kraktak](https://github.com/snstac/kraktak) | — |
| APRS amateur radio | [aprscot](https://github.com/snstac/aprscot) | — |
| Weather stations | [windtak](https://github.com/snstac/windtak) | — |
| CoT routing / TAK Server bridging | [charontak](https://github.com/snstac/charontak) | — |

All gateways are built on [PyTAK](https://github.com/snstac/pytak), speak
**Cursor on Target (CoT)** to **ATAK, WinTAK, iTAK, TAK Server, and Mesh SA**, ship as
signed Debian/RPM packages at [snstac.github.io/packages](https://snstac.github.io/packages),
and come pre-installed on [AryaOS](https://github.com/snstac/aryaos), the
situational-awareness OS for Raspberry Pi.


## License & Copyright

Copyright Sensors & Signals LLC <https://www.snstac.com>. Licensed under the
Apache License, Version 2.0.
