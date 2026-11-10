# Changelog

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
