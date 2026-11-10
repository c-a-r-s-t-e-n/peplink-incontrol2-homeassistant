# Changelog

## 1.0.0 — 2026-11-10

First stable-labelled release, preserving all existing v0.1.x entity unique IDs.

- Introduce a separate **Last known GPS (historical)** map tracker while retaining the existing **GPS location** tracker exclusively for recent, online positions.
- Add **GPS last reported** and **GPS position current** sensors; mark tracker attributes with UTC timestamp, age, freshness and source type.
- Round reported GPS speed to two decimal places.
- Add German/English diagnostic messages to distinguish absent site-survey dates, missing reports and unavailable cellular measurements.
- Keep numeric site-survey cell count unknown when no scan has been performed (never misrepresent no report as zero detected cells).
- Document all entities and likely entity-ID patterns, with offline and low-signal notification examples, map cards, one-click HACS installation, upgrade/removal, security and separate MIT license/copyright section.
- Add Home Assistant minimum-version, MIT, HACS category, release, validation and issue badges.
- Add unit coverage for GPS freshness, stale positions, timezone parsing, diagnostics, and previously verified LTE/5G WAN quality selection.
- Introduce a gated stable GitHub release workflow validating Python, tests, hassfest and HACS before tag creation.
- Keep temporary, account-specific PowerShell scripts **out of the public repository**.

**Operational limitations:** Historical WAN samples and site surveys depend on InControl 2 reporting; the integration is read-only and not suitable as the sole source for safety-critical alerting. The declared minimum Home Assistant version has not been exhaustively tested.


## 0.1.0-beta.5 — 2026-11-10

- Confirmed from anonymized live diagnostics that WAN quality data includes real LTE and 5G cellular samples, while non-cellular WANs carry only time/position metadata.
- Discover the WAN IDs from the WAN-quality report itself, not only from device inventory.
- Select the most recent reported historical day for routers that are offline.
- Retain the latest samples containing real cellular metrics; limit in-memory report size instead of caching thousands of samples per WAN.
- Sort cloud samples by their timestamp before selecting recent values.
- Separate pure sample selection into a tested module; add regression tests for LTE, 5G, unknown carriers and empty WANs.
- Attach the source report day to WAN diagnostic sensor attributes, so historical readings can be distinguished from live values.
- One-off diagnostic PowerShell scripts remain outside the public repository.

**Note:** Signal readings reflect Peplink cloud history and may be stale. A successful CI run does not replace validation of the updated version on real devices.



## 0.1.0-beta.4 — 2026-11-10

- Fix WAN signal selection: prefer real cellular sample values per measurement field rather than the latest unrelated WAN record
- Improve survey result parsing and WAN history entry handling
- Add WAN signal and tower survey diagnostic sensors to explain missing data
- Expand README: full entity reference with update intervals, one-click HACS link, example offline notification, upgrade, discovery, removal, security and trademarks
- Add sanitized read-only WAN quality PowerShell diagnostic probe
- No credentials or device-specific data embedded in code
- **Known limitation:** Signal measurements and site surveys still depend on actual cloud reports; test with the sanitized probe if sensors remain unknown



## 0.1.0-beta.3 — 2026-11-10

- Correct documented date-range parameters for cellular WAN quality, site surveys and availability
- Discover WAN IDs from actual device interfaces and bandwidth reports
- Resolve per-WAN up/down history instead of showing metadata-only unknown values
- Support per-device detail payloads and per-WAN status entities
- Add connected-client count, GPS speed, GPS altitude and availability report sensor
- Preserve last valid optional report results when the API temporarily returns no data
- Do not fabricate signal readings, scans or past uptime when Peplink has no report

**Live status:** CI checks available; advanced responses and signal samples still require a new on-device validation cycle.


## 0.1.0-beta.2 — 2026-11-10

- Interpret GPS timestamps in the configured InControl group timezone
- Suppress GPS device tracker coordinates older than 30 minutes or from offline devices
- Retain separate WAN-quality samples for multiple WAN interfaces (up to eight)
- Correct daily/monthly report period selection for group timezone
- Add Home Assistant `network` integration category and an original icon
- Add GitHub validation workflow (Python, hassfest and HACS checks)
- Keep read-only API access and avoid embedding credentials in the repository

**Known limitations:** WAN, site survey, event, and usage response structures need additional live validation. HACS validation also requires the repository owner to configure GitHub topics and description.


## 0.1.0-beta.1 — Unreleased candidate

- OAuth2 client credentials and automatic token refresh
- Cloud device discovery, online status, GPS tracker, basic diagnostic sensors
- Optional requests for WAN quality, bandwidth, tower scans, WAN history and events

**Beta warning:** Optional endpoint response shapes have not yet been verified
against live devices; values may be missing or incorrect. No guarantee of current
GPS location. Do not rely on this integration for critical alerts.
