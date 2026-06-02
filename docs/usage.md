# Usage

## Running the bridge

```bash
kraktak -c kraktak.conf
```

Or via environment variables only:

```bash
COT_URL=udp://239.2.3.1:6969 \
FEED_URL=http://192.168.50.5:8081/DOA_value.html \
COT_TYPES=bearing_line,lob,sensor \
kraktak
```

As a service (Debian package installs this for you):

```bash
sudoedit /etc/default/kraktak
sudo systemctl enable --now kraktak
sudo journalctl -u kraktak -f
```

## Controlling the KrakenSDR from TAK

Set `ENABLE_CONTROL = true` and connect `COT_URL` to a TAK Server over
`tcp://`/`tls://` (multicast is transmit-only). Then send a GeoChat message:

```
kraken freq 462.5625      # tune center frequency (MHz)
kraken gain 16.6          # uniform gain (dB)
kraken vfo 0 467000000    # VFO-0 frequency (Hz)
kraken bw 0 12500         # VFO-0 bandwidth (Hz)
kraken coord 34.70 -86.65 # station coordinates
kraken status             # report current state
```

You can also send a CoT event carrying a control detail:

```xml
<detail>
  <__krakencmd action="set_frequency" freq="146.52"/>
</detail>
```

KrakTAK replies with a GeoChat acknowledgement and validates frequency/gain
against the KrakenSDR's accepted ranges before applying.

### Control backends

KrakTAK auto-detects the best available path:

1. `api_agent` - the [kraken_api_agent](https://github.com/ghostop14/kraken_api_agent)
   REST API on `:8181` (install with `extras/install_kraken_api_agent.sh`).
2. `middleware` - the krakensdr_doa middleware on `:8042`.
3. `settings_json` - portable `settings.json` upload on `:8081` (sets
   `en_remote_control` on first push).

Force a specific one with `CONTROL_BACKEND`.

## Dashboard

```bash
kraktak-dashboard -c kraktak.conf
```

Open `http://<host>:8000/` for live KrakenSDR settings, the latest DOA, and
manual tune/gain/coordinate controls.
