# Peplink InControl 2 Monitor for Home Assistant

[![Validate](https://github.com/c-a-r-s-t-e-n/peplink-incontrol2-homeassistant/actions/workflows/validate.yml/badge.svg)](https://github.com/c-a-r-s-t-e-n/peplink-incontrol2-homeassistant/actions/workflows/validate.yml)
[![Latest release](https://img.shields.io/github/v/release/c-a-r-s-t-e-n/peplink-incontrol2-homeassistant?include_prereleases&label=release)](https://github.com/c-a-r-s-t-e-n/peplink-incontrol2-homeassistant/releases)

**Community-developed, read-only Home Assistant integration for remote Peplink routers using the official InControl 2 API.** No direct LAN access, public router IP or VPN is necessary.

> **Early beta.** The latest published release is [v0.1.0-beta.4](https://github.com/c-a-r-s-t-e-n/peplink-incontrol2-homeassistant/releases/tag/v0.1.0-beta.4). The development branch can be ahead of that release; check [all releases](https://github.com/c-a-r-s-t-e-n/peplink-incontrol2-homeassistant/releases) and [CHANGELOG](CHANGELOG.md). Historical WAN quality and cell surveys remain experimental. Do not depend on this integration alone for emergency, security or safety-critical decisions.

## Quick installation

[![Open HACS repository in Home Assistant](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=c-a-r-s-t-e-n&repository=peplink-incontrol2-homeassistant&category=integration)

1. Have [HACS](https://www.hacs.xyz/) installed and configured.
2. Use the button above, choose your Home Assistant instance, and add the custom integration repository. Alternatively, in HACS open **Custom repositories** and enter `https://github.com/c-a-r-s-t-e-n/peplink-incontrol2-homeassistant` with category **Integration**.
3. Install the integration in HACS, selecting the latest beta/pre-release if you want beta updates. Restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration → Peplink InControl 2 Monitor**.
5. Supply **your own** Client ID and Client Secret from InControl 2 → **Client Applications**. Use an enabled **Bearer** client. No website or OAuth redirect URI is needed.

**Requirements:** Home Assistant 2025.1+ (declared minimum, not fully tested), a Peplink InControl 2 account, API permissions for the target organizations and outbound HTTPS connectivity.

## Features and polling

A shared coordinator polls **organization, group, router status and GPS every 120 seconds**. More expensive **daily/monthly bandwidth, availability, event history, WAN diagnostics and survey reports** are requested on the first refresh and then every **10 coordinator cycles (~20 minutes)**. Peplink cloud reporting and retries can introduce additional latency. These are **request intervals**, not guaranteed sample ages.

New routers, WAN interfaces and other entities are currently registered **at integration setup/reload**, not dynamically added during a poll.

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
| GPS location | Device tracker | coordinates | home / away | 120 s |
| Each WAN interface status (dynamic) | Sensor | text | Connected to Telekom.de / Disabled | 120 s |

**Important interpretation:** `Last online` is a Peplink-reported field and may be an older session timestamp even while Cloud online is true. The GPS tracker accepts only non-static coordinates from an *online* device whose GPS report is no older than **30 minutes**; always inspect GPS age before relying on location. WAN quality is a historical report, not guaranteed live modem telemetry. Interface status is distinct from the WAN quality history. A cell tower scan is a historical site survey, **not necessarily the connected radio cell**. WAN history with zero records is not proof of zero outages outside the queried time window. Bandwidth values are those reported by Peplink in MB; distinguish the report's period from real-time traffic rates.

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

## Upgrading, discovering new routers and uninstalling

**Upgrade:** In HACS open **Peplink InControl 2 Monitor → Update / Redownload**, select the desired release (enable beta/pre-release versions where necessary), install and **restart Home Assistant**. Check the installed integration version and [release notes](https://github.com/c-a-r-s-t-e-n/peplink-incontrol2-homeassistant/releases). HACS may display a short commit hash if a development branch was installed rather than a tagged release.

**A new router or WAN is missing?** First verify the device is visible to your API client's InControl organization. Then use **Settings → Devices & services → Peplink InControl 2 Monitor → ⋮ → Reload**. This rebuilds the entity set for all currently discovered routers and interfaces. If still missing, restart Home Assistant and check the integration logs. You should **not need to delete the existing integration** merely to discover additional routers. If the account has a new organization, ensure the API client has permission to view it.

**Uninstall:** In **Settings → Devices & services**, remove the Peplink InControl 2 integration/config entry first (removes its HA entities). Then remove the repository/integration from **HACS** and restart Home Assistant. Historical data and custom dashboards may remain in Home Assistant Recorder/backups; clean those separately if required. Also **revoke/delete the OAuth client in InControl 2** if it is no longer needed. Removing the HACS files alone does not revoke cloud credentials.

## Privacy, credentials and security

- The Client ID and Client Secret are entered in Home Assistant and held in its **private config-entry storage** (normally under `/config/.storage/`, including `core.config_entries`). That area should not be edited manually or published. The integration does not embed credentials in GitHub, the README or example files.
- Home Assistant makes outbound **HTTPS** requests to Peplink's InControl 2 API for OAuth authentication and device monitoring. The API receives the client credentials at authentication and subsequently bearer access tokens, resource identifiers and query parameters necessary for the reports. GPS, WAN, clients and usage data are **returned** from the cloud to your Home Assistant instance.
- This integration invokes **GET/read-only** resource endpoints. The OAuth token is requested through POST, but the integration does not change router/firewall configuration or initiate a site survey.
- Home Assistant can store returned telemetry, GPS locations, entity histories and events locally in Recorder, backups and diagnostics. Protect access to dashboards, logs, backups and your Home Assistant instance, especially if you publish GPS tracking.
- Never share tokens, Client Secrets, WAN IPs, serial numbers, organization IDs, router locations, or raw API/event responses in public issues. Sanitized structural diagnostics are preferred. Rotate a leaked Client Secret in InControl 2.

## Troubleshooting

- **Unknown cellular signals:** An available WAN quality timestamp does not mean the selected sample has RSRP/RSRQ/SINR/RSSI. Check **WAN signal diagnostics** for the difference between missing reports, empty samples and reports without cellular fields. Individual cellular values are selected only from samples that actually include that field.
- **Unknown tower survey:** Check **Tower survey diagnostics**. Not all routers have completed a site survey; survey results are not equivalent to the serving cell. The integration never initiates scans.
- **Offline router:** Historical data may remain in InControl 2. Prefer the Cloud online sensor for connectivity decisions.
- **Cloud errors or `PENDING`:** InControl 2 may temporarily defer a report. Enable debug logs for `custom_components.peplink_incontrol2` and remove sensitive values before sharing.
- **New device not shown:** Reload the integration to register its entities.
- **Version is a commit SHA:** Install a selected tagged beta release in HACS rather than the development branch.

## Development and project links

- [GitHub repository](https://github.com/c-a-r-s-t-e-n/peplink-incontrol2-homeassistant)
- [Releases and downloads](https://github.com/c-a-r-s-t-e-n/peplink-incontrol2-homeassistant/releases)
- [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) · [Security policy](SECURITY.md)
- Syntax check: `python -m compileall -q custom_components`. Pull requests are checked with HACS, hassfest and Python compilation. API response schemas should be validated against anonymized live output before claiming support.

## Disclaimer and trademarks

This is **independent community software**, provided under the [MIT License](LICENSE), **not an official Peplink product** and **not affiliated with, sponsored by or endorsed by Peplink**. *Peplink*, *InControl* and related product names/logos are trademarks of their respective owners. The integration uses an **independently designed icon**, not an official Peplink logo; no ownership over third-party marks is claimed. Functionality, device support and cloud APIs can change; use at your own risk. No warranty is provided.
