![Peplink InControl 2 — network visibility for Home Assistant](https://raw.githubusercontent.com/c-a-r-s-t-e-n/peplink-incontrol2-homeassistant/main/docs/assets/header.png)

# Peplink InControl 2 Monitor for Home Assistant

[![Validate](https://github.com/c-a-r-s-t-e-n/peplink-incontrol2-homeassistant/actions/workflows/validate.yml/badge.svg)](https://github.com/c-a-r-s-t-e-n/peplink-incontrol2-homeassistant/actions/workflows/validate.yml)
[![Latest release](https://img.shields.io/github/v/release/c-a-r-s-t-e-n/peplink-incontrol2-homeassistant?label=stable)](https://github.com/c-a-r-s-t-e-n/peplink-incontrol2-homeassistant/releases)
[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Home Assistant 2025.3+](https://img.shields.io/badge/Home%20Assistant-%E2%89%A52025.3-blue)](https://www.home-assistant.io/)
[![Marketplace](https://img.shields.io/badge/Home%20Assistant-Marketplace-18bcf2)](https://www.home-assistant.io/integrations/marketplace/)
[![Issues](https://img.shields.io/github/issues/c-a-r-s-t-e-n/peplink-incontrol2-homeassistant)](https://github.com/c-a-r-s-t-e-n/peplink-incontrol2-homeassistant/issues)

**Community-developed, read-only Home Assistant integration for remote Peplink routers using the official InControl 2 API.** No direct LAN access, public router IP or VPN is necessary.

| Network health | Cellular insight | Remote visibility |
|---|---|---|
| Cloud connectivity and each WAN's status | RSRP, RSRQ, SINR, RSSI per reported WAN | Current and explicitly historical GPS trackers |
| Clients, uptime, firmware and usage | Carrier, band, bearer and cell identity | Timestamped reports and availability |
| Historical latency per WAN | Most recent recorded tower survey | Automatic device and WAN discovery |

## Requirements

- **Home Assistant 2025.3 or newer**. CI tests 2025.3.4 and 2026.11.2; intermediate versions are not individually certified.
- A Peplink InControl 2 account with access to the required organizations and enabled API client credentials.
- Outbound HTTPS to `api.ic.peplink.com`. No inbound port, local router password or VPN is required.

<!-- ha-marketplace:exclude-start -->
## Installation

[![Open repository in Home Assistant](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=c-a-r-s-t-e-n&repository=peplink-incontrol2-homeassistant&category=integration)

1. In **Settings → Marketplace**, add `https://github.com/c-a-r-s-t-e-n/peplink-incontrol2-homeassistant` as a custom **Integration** repository. On older Home Assistant versions, use **HACS → Custom repositories**.
2. Install the latest stable release and **restart Home Assistant**.
3. Open **Settings → Devices & services → Add integration → Peplink InControl 2 Monitor**.
4. Enter your own **Client ID** and **Client Secret**.

For manual installation, copy `custom_components/peplink_incontrol2/` to `/config/custom_components/peplink_incontrol2/` and restart.
<!-- ha-marketplace:exclude-end -->

## Configuration

Open [InControl 2](https://incontrol2.peplink.com/), click your profile from an organization or group overview, and create an enabled **Bearer** client under **Client Applications**. The integration uses OAuth client credentials; no redirect URI is needed. Use credentials dedicated to your own installation and with access only to the required organizations. Public Peplink cloud is supported; private InControl appliances and alternative regional hosts are not configurable.

An expired or rejected secret opens Home Assistant's reauthentication flow. Replace the secret there to preserve the integration entry and entity IDs. A different Client ID requires a new integration entry.

## Refresh and performance

| Data | Schedule |
|---|---|
| Organizations, groups, device details and GPS | Every 120 seconds, after the preceding refresh completes |
| Bandwidth, events, availability, WAN history, quality and survey reports | First requested on the second refresh; then at least 20 minutes between successful report batches |
| Partial optional reports | Eligible for retry after 120 seconds |

The initial setup fetches inventory and GPS only. **Historical sensors can remain unknown for the first few minutes.** Devices and WAN entities discovered later are added automatically. No integration reload is required.

All entities share one coordinator. Calls are serialized and paced to at most 10 resource requests/second per entry; actual throughput depends on network latency. HTTP 429 stops the refresh and respects `Retry-After` before another request. Only one token renewal is attempted after HTTP 401. Responses are bounded at 32 MiB, and quality histories are reduced to a small set of recent samples while preserving the latest available value of each supported field. Removed devices are pruned from memory after a successful inventory refresh.

**Report coverage** describes the latest report batch: `waiting` before the first batch, `complete` when no request failed or remained pending, and `partial` otherwise. It is not a guarantee of complete cloud history. Empty reports remain distinguishable from zero measurements. **Reports last requested** records the UTC request time, not the measurement time. Optional failures can retain previous readings; inspect source timestamps before using them.

## Entity reference

Examples are illustrations, not guarantees. Each router has its own entity IDs, determined by Home Assistant. `Unknown` means no usable value was returned (not automatically zero). Diagnostic and unavailable device features vary by model and cloud reporting capabilities.

| Entity (display name) | HA type | Unit | Example | Requested every |
|---|---|---|---|---|
| Cloud online | Binary sensor (connectivity) | on/off | on | 120 s |
| Cloud status | Sensor | text | online | 120 s |
| Firmware | Sensor (diagnostic) | text | 8.6.1 build 6572 | 120 s |
| Last online | Sensor | text | 2026-10-04T03:47:20 | 120 s |
| Uptime | Sensor | s | 3256916 | 120 s |
| PepVPN peers | Sensor | count | 5 | 120 s |
| Connected clients | Sensor | count | 4 | 120 s |
| Prime expiry | Sensor (diagnostic) | text/date string | 2027-04-09T00:00:00 | 120 s |
| Subscription expiry | Sensor (diagnostic) | text/date string | 2027-03-26T00:00:00 | 120 s |
| Event log entries | Sensor | count | 28 | ~20 min |
| Last event | Sensor | text | LAN | ~20 min |
| WAN history entries | Sensor | count | 0 | ~20 min |
| Last survey cell count | Sensor | count | 6 | ~20 min |
| Last tower survey | Sensor | text/time | 2026-11-10T12:00:00 | ~20 min |
| WAN RSRP latest | Sensor | dBm | -93 | ~20 min |
| WAN RSRQ latest | Sensor | dB | -11 | ~20 min |
| WAN SINR latest | Sensor | dB | 14 | ~20 min |
| WAN RSSI latest | Sensor | dBm | -68 | ~20 min |
| WAN carrier latest | Sensor | text | Telekom.de | ~20 min |
| WAN band latest | Sensor | text | n78 | ~20 min |
| WAN cell ID latest | Sensor | numeric ID | (may be unknown) | ~20 min |
| WAN bearer latest | Sensor | text | LTE | ~20 min |
| WAN quality last sample | Sensor | text/time | 2026-11-10T19:20:29 | ~20 min |
| WAN signal diagnostics | Sensor | text | No cellular fields in samples | ~20 min |
| Tower survey diagnostics | Sensor | text | No survey dates reported | ~20 min |
| Availability latest | Sensor | % | 100 | ~20 min |
| Daily upload | Sensor | MB | 150.2 | ~20 min |
| Daily download | Sensor | MB | 862.3 | ~20 min |
| Monthly upload | Sensor | MB | 8200.5 | ~20 min |
| Monthly download | Sensor | MB | 19430.7 | ~20 min |
| GPS age | Sensor | min | 2 | 120 s |
| GPS speed | Sensor | km/h | 0 | 120 s |
| GPS altitude | Sensor | m | 271.7 | 120 s |
| GPS location (current) | Device tracker | coordinates | home / away | 120 s |
| Last known GPS (historical) | Device tracker | coordinates | last known location | 120 s |
| GPS last reported | Sensor | ISO 8601 UTC | 2026-11-10T19:58:00+00:00 | 120 s |
| GPS position current | Sensor | yes/no | yes | 120 s |
| Each WAN latency latest | Sensor | ms | 35 | ~20 min |
| Each WAN RSRP / RSRQ / SINR / RSSI latest | Sensor | dBm / dB | -85 | ~20 min |
| Report coverage | Diagnostic sensor | text | complete / partial / waiting | Each report batch |
| Reports last requested | Diagnostic sensor | UTC timestamp | ISO 8601 | Each report batch |
| Each WAN interface status (dynamic) | Sensor | text | Connected to Telekom.de / Disabled | 120 s |

Per-WAN quality entities are created only after their corresponding field is actually reported. Each has its own `sample_time`, `sample_epoch`, `report_day` and `historical` attributes. Existing aggregate cellular entities are retained for automation compatibility. No extra cloud requests are needed for the per-WAN values.

### Entity IDs and unique identifiers

Home Assistant generates entity IDs from the device name and entity label, for example **`binary_sensor.max_br1_16d5_studio_cloud_online`**, **`sensor.max_br1_16d5_studio_wan_rsrp_latest`**, **`sensor.max_br1_16d5_studio_gps_age`**, **`device_tracker.max_br1_16d5_studio_gps_location`** and **`device_tracker.max_br1_16d5_studio_last_known_gps_historical`**. These are **illustrations**, not fixed entity IDs: Home Assistant may append suffixes, users can rename devices/entities, and translated names can affect initial generation. Always copy the actual entity ID from **Settings → Devices & services → Peplink InControl 2 Monitor → device → entity** or **Developer tools → States**.

Internally, each router has a stable unique ID based on organization, group and device; every existing entity retains its previous unique-ID suffix on upgrade. The new historical tracker uses `_gps_last_known`, while the existing current tracker continues using `_gps`.

**Important interpretation:** `Last online` is a Peplink-reported field and may be an older session timestamp even while Cloud online is true. The GPS tracker accepts only non-static coordinates from an *online* device whose GPS report is no older than **30 minutes**; always inspect GPS age before relying on location. WAN quality is a historical report, not guaranteed live modem telemetry. InControl can return very large reports where most non-cellular WAN records have no RSRP/RSRQ/SINR fields. The integration uses the WAN list from the quality report and retains only the most recent relevant cellular samples; the WAN quality sensors include a `report_day` attribute to identify the source date. Offline routers can still expose their last historical LTE/5G readings, which must not be treated as live reception. Interface status is distinct from the WAN quality history. A cell tower scan is a historical site survey, **not necessarily the connected radio cell**. WAN history with zero records is not proof of zero outages outside the queried time window. Bandwidth values are those reported by Peplink in MB; distinguish the report's period from real-time traffic rates.

## Example: notify when a Peplink goes offline

In **Developer tools → States**, find the **Cloud online** binary sensor belonging to your router and replace the example entity IDs below. Also replace the notification action with your Android Companion App target. The automation requires 5 minutes of continuous offline state to reduce transient false alarms.

```yaml
alias: "Peplink: router offline"
description: "Alert only on sustained loss of cloud connectivity"
triggers:
  - trigger: state
    entity_id: binary_sensor.REPLACE_WITH_PEPLINK_CLOUD_ONLINE
    to: "off"
    for: "00:05:00"
actions:
  - action: notify.mobile_app_REPLACE_WITH_YOUR_PHONE
    data:
      title: "Peplink offline"
      message: >-
        InControl 2 reports the router offline for at least 5 minutes.
        Last reported GPS age:
        {{ states('sensor.REPLACE_WITH_PEPLINK_GPS_AGE') }} minutes.
        Location may be stale: do not assume the last GPS position
        represents its current location.
mode: single
```

For **location-triggered** actions, verify both that the device is online and the GPS age sensor is numeric and **less than 30 minutes**. Do not use an old position from an offline router as live tracking. For important alerts, cross-check InControl 2 directly and allow for cloud reporting delays.

## More examples: cellular signal alert and GPS map

### Weak cellular signal alert

This sample alerts when the reported RSRP stays **below −110 dBm for 10 minutes**. WAN quality is a historical InControl report, normally refreshed every ~20 minutes, so this is **not a real-time RF alarm**. The `report_day` attribute helps identify old recordings. Replace both entity IDs and the notification action with the actual IDs from your Home Assistant instance.

```yaml
alias: "Peplink: poor cellular RSRP"
triggers:
  - trigger: numeric_state
    entity_id: sensor.REPLACE_WITH_PEPLINK_WAN_RSRP_LATEST
    below: -110
    for: "00:10:00"
conditions:
  - condition: state
    entity_id: binary_sensor.REPLACE_WITH_PEPLINK_CLOUD_ONLINE
    state: "on"
actions:
  - action: notify.mobile_app_REPLACE_WITH_YOUR_PHONE
    data:
      title: "Peplink: poor cellular signal"
      message: >-
        Reported RSRP: {{ states('sensor.REPLACE_WITH_PEPLINK_WAN_RSRP_LATEST') }} dBm.
        Source date: {{ state_attr('sensor.REPLACE_WITH_PEPLINK_WAN_RSRP_LATEST', 'report_day') }}.
        This is historical cloud data, not live modem telemetry.
mode: single
```

### Map with current and last-known position

Add a **Map** card from the dashboard editor or paste the configuration below. This intentionally includes two different trackers per router: **GPS location** is limited to fresh online positions, while **Last known GPS (historical)** remains visible for older reports. The latter may show a stale location and must **never** drive live safety/location alarms.

```yaml
type: map
title: Peplink routers – current and historical
entities:
  - entity: device_tracker.REPLACE_WITH_STUDIO_GPS_LOCATION
  - entity: device_tracker.REPLACE_WITH_RUCKSACK_GPS_LOCATION
  - entity: device_tracker.REPLACE_WITH_STUDIO_LAST_KNOWN_GPS
  - entity: device_tracker.REPLACE_WITH_RUCKSACK_LAST_KNOWN_GPS
hours_to_show: 24
auto_fit: true
```

The tracker attributes `last_reported_utc`, `gps_age_minutes`, `position_is_current` and `position_type` provide context. A separate **GPS last reported** sensor contains the cloud timestamp. Because two markers can overlap when the position is fresh, you may prefer a second dashboard map exclusively for historical trackers. Home Assistant Recorder retains state history only according to your configured retention settings.

## Upgrading, discovering new routers and uninstalling

**Upgrade:** Install the latest stable release through Marketplace or HACS and restart Home Assistant. Keep the existing integration entry to preserve credentials, renamed entities and automations. Existing unique IDs are unchanged.

**New router missing?** Check API permissions and wait for the next inventory cycle. WAN quality entities appear only after their first usable report. A router moved between groups receives a different inventory identity because its organization/group/device key changes.

**Uninstall:** In **Settings → Devices & services**, remove the Peplink InControl 2 integration/config entry first (removes its HA entities). Then remove the repository/integration from **Marketplace/HACS** and restart Home Assistant. Historical data and custom dashboards may remain in Home Assistant Recorder/backups; clean those separately if required. Also **revoke/delete the OAuth client in InControl 2** if it is no longer needed. Removing the HACS files alone does not revoke cloud credentials.

## Privacy, credentials and security

- The Client ID and Client Secret are entered in Home Assistant and held in its **private config-entry storage** (normally under `/config/.storage/`, including `core.config_entries`). That area should not be edited manually or published. The integration does not embed credentials in GitHub, the README or example files.
- Home Assistant makes outbound **HTTPS** requests to Peplink's InControl 2 API for OAuth authentication and device monitoring. The API receives the client credentials at authentication and subsequently bearer access tokens, resource identifiers and query parameters necessary for the reports. GPS, WAN, clients and usage data are **returned** from the cloud to your Home Assistant instance.
- This integration invokes **GET/read-only** resource endpoints. The OAuth token is requested through POST, but the integration does not change router/firewall configuration or initiate a site survey.
- Home Assistant can store returned telemetry, GPS locations, entity histories and events locally in Recorder, backups and diagnostics. Protect access to dashboards, logs, backups and your Home Assistant instance, especially if you publish GPS tracking.
- Never share tokens, Client Secrets, WAN IPs, serial numbers, organization IDs, router locations, or raw API/event responses in public issues. Sanitized structural diagnostics are preferred. Rotate a leaked Client Secret in InControl 2.

## Troubleshooting

- **Unknown cellular signals:** An available WAN quality timestamp does not mean the selected sample has RSRP/RSRQ/SINR/RSSI. Check **WAN signal diagnostics** for the difference between missing reports, empty samples and reports without cellular fields. Individual cellular values are selected only from samples that actually include that field.
- **Unknown tower survey:** Check **Tower survey diagnostics**. A confirmed empty report-day list is displayed as **No site survey recorded** (or **Kein Site Survey vorhanden** with German Home Assistant language). The numeric *Last survey cell count* stays unknown if no scan was ever performed; zero would incorrectly claim a measured zero-cell scan. A survey is not equivalent to the serving cell. The integration never initiates scans.
- **Offline router:** Historical data may remain in InControl 2. Prefer the Cloud online sensor for connectivity decisions.
- **Cloud errors or `PENDING`:** InControl 2 may temporarily defer a report. Enable debug logs for `custom_components.peplink_incontrol2` and remove sensitive values before sharing.
- **New device not shown:** Check API permissions and allow an inventory refresh; entities are discovered automatically.
- **Version is a commit SHA:** Install a tagged stable release through Marketplace/HACS.

## Diagnostics and support

Download the integration diagnostics from **Settings → Devices & services**. The export contains only counts, report coverage and polling metadata; no raw responses, credentials, names, serial numbers or GPS coordinates.

**Missing Marketplace icon:** The release includes local light/dark icons and logos. Restart after installing. Before installation, the catalogue/CDN may still show a placeholder for custom repositories that are not indexed; the repository cannot force that external cache to refresh.

[API mapping and limits](docs/API.md) · [Branding](docs/BRANDING.md)

<!-- ha-marketplace:exclude-start -->
## Development and project links

- [GitHub repository](https://github.com/c-a-r-s-t-e-n/peplink-incontrol2-homeassistant)
- [Releases and downloads](https://github.com/c-a-r-s-t-e-n/peplink-incontrol2-homeassistant/releases)
- [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) · [Security policy](SECURITY.md)
- Development: `pip install -r requirements-dev.txt`, then `ruff check .`, `ruff format --check .` and `pytest -q`.
- CI runs the tests with real Home Assistant classes at the minimum tested and current versions, plus hassfest and HACS validation. Synthetic response tests do not replace a live test with each router model and cloud subscription.
<!-- ha-marketplace:exclude-end -->

## Disclaimer and trademarks

This is **independent community software**, provided under the [MIT License](LICENSE), **not an official Peplink product** and **not affiliated with, sponsored by or endorsed by Peplink**. *Peplink*, *InControl* and related product names/logos are trademarks of their respective owners. The integration uses an **independently designed icon**, not an official Peplink logo; no ownership over third-party marks is claimed. Functionality, device support and cloud APIs can change; use at your own risk. No warranty is provided.

## License

This project is distributed under the **[MIT License](LICENSE)**. You may use, modify and redistribute the code under its terms. Include the original copyright and license notices when redistributing substantial portions.

Copyright (c) 2026 **c-a-r-s-t-e-n and contributors**.

