# KrakTAK — Agent Handoff

Operational notes for the next agent working on the KrakenSDR → TAK bridge.

## TL;DR

- **What:** Polls KrakenSDR `DOA_value.html` CSV, emits Cursor-on-Target (CoT) per
  detection, optional TAK→Kraken control plane.
- **Repo:** https://github.com/snstac/kraktak
- **Shared CoT builders:** https://github.com/snstac/takline (`v0.1.2+`)
- **Recent change:** Assumed-range **target fix** renderings (`spi`,
  `target_range_bearing`) aligned with SkyScanTAK / RedRock; **spot POI off by
  default**.

## Target fix (SkyScanTAK pattern)

A lone DOA has no range. KrakTAK places an **assumed-range fix** along the bearing
using `LOB_LENGTH_M` (or `TARGET_FIX_RANGE_M` override).

| `COT_TYPES` token | CoT type | Default? | Notes |
|-------------------|----------|----------|-------|
| `spi` | `b-m-p-s-p-i` | **yes** | Contact + parent `<link>` only (no `<sensor>` on SPI). |
| `target_range_bearing` | `u-rb-a` | **yes** | Station → fix. Metres, `northRef=1`, parent link for CloudTAK. |
| `spot_poi` | `b-m-p-s-m` | **no** | Add to `COT_TYPES` to enable colored map POI. |

Implementation: `src/kraktak/functions.py` delegates to takline:
- `takline.build_spi_link_event`
- `takline.build_target_range_bearing_event`
- `takline.build_track_poi_event` (spot POI only)

Parent link points at the Kraken station marker (`a-f-G-U-C`, uid
`kraktak-1.KrakenSDR.{station}`).

### Default `COT_TYPES`

```ini
COT_TYPES=lob,bearing_line,spi,target_range_bearing
```

Other tokens: `sensor`, `range_bearing` (LOB-length R&B, distinct from target R&B),
`cep`.

### Config knobs

| Setting | Purpose |
|---------|---------|
| `LOB_LENGTH_M` | Bearing-line length **and** default assumed fix range (m) |
| `TARGET_FIX_RANGE_M` | Override assumed fix range for `spi` / `target_range_bearing` |
| `COT_POI_COLOR_ARGB` / `COT_POI_ICONSET` | Spot POI styling when enabled |
| `COT_TARGET_RB_COLOR` / `COT_TARGET_RB_STROKE_WEIGHT` | Target R&B appearance |
| `COT_SENSOR_TYPE` | Parent link type (default `a-f-G-U-C`) |

## takline dependency

```ini
# setup.cfg
takline @ git+https://github.com/snstac/takline.git@v0.1.2
```

Local dev without install:

```bash
PYTHONPATH=/path/to/takline/src:src python3 -m pytest tests/test_functions.py
```

When changing target-fix CoT shapes, update **takline first**, tag a release,
then bump the git pin here. RedRock (`ampledata/redrock-rdf-client`) vendors the
same takline sources.

## Code map

| Path | Role |
|------|------|
| `src/kraktak/functions.py` | All CoT builders (`COT_BUILDERS` dict) |
| `src/kraktak/classes.py` | `KrakTAKWorker` — poll DOA, call builders |
| `src/kraktak/constants.py` | Defaults including `DEFAULT_COT_TYPES` |
| `kraktak-example.conf` | Commented template |
| `tests/test_functions.py` | Builder + SPI/R&B layout tests |

## Testing

```bash
make test
# or
PYTHONPATH=src python3 -m pytest tests/test_functions.py -q
```

Key tests: `test_spi_has_parent_link_without_sensor_payload`,
`test_target_range_bearing_cot_skyscan_layout`, `test_default_cot_types_include_spi_and_target_rb`.

## Related projects

- **SkyScanTAK** — camera/ADS-B SPI + R&B reference (`cot/bridge/main.py`)
- **RedRock** — DRS RDF monitor using same takline builders for marine DF
- **takline** — shared `build_spi_link_event`, `build_target_range_bearing_event`

## Recent git history

- `c67712f` — Add SPI / target R&B builders (10.2.0)
- `0f8eef2` — Delegate to takline 0.1.2 (10.2.1)

## Open follow-ups

- Publish `takline` to PyPI so CI does not need the git URL pin.
- Consider deprecating the older `range_bearing` token in docs if `target_range_bearing`
  supersedes it for map display (they differ: km vs m, no parent link).
- Multi-station LOB intersection for real fix range (vs assumed `LOB_LENGTH_M`).
