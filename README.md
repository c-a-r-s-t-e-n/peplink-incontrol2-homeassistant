# Peplink InControl 2 Monitor for Home Assistant

[![Validate](https://github.com/c-a-r-s-t-e-n/peplink-incontrol2-homeassistant/actions/workflows/validate.yml/badge.svg)](https://github.com/c-a-r-s-t-e-n/peplink-incontrol2-homeassistant/actions/workflows/validate.yml)

**Community-maintained, read-only beta integration** for monitoring remote
Peplink routers through the official InControl 2 cloud API (no local LAN or VPN
required). Not affiliated with or endorsed by Peplink.

> **Status: early beta / not production-validated.** The optional API response
> schemas for WAN, bandwidth, surveys and events require live verification.
> Do not use this integration as the sole source for important outages or
> location-based safety decisions.

## Features

- OAuth2 client credentials, automatic token refresh
- Auto-discovery of accessible organizations, groups and routers at setup
- Per-router online binary sensor, firmware, last online and other basic data
- GPS `device_tracker` for devices with cloud location data
- Experimental optional sensor reads for WAN quality, cellular signal, site
  survey, bandwidth, WAN history and event logs

**GPS caution:** InControl can retain old GPS positions; the integration does
not expose location while the router is offline, but even an online router's
coordinates can be stale. Inspect its timestamp before automating on GPS.

**Polling:** Device status is polled periodically; detailed API requests are
less frequent. Device discovery is presently performed during the first setup,
so newly added devices may require an integration reload.

## Requirements

- Home Assistant 2025.1 or later (declared minimum; not yet fully tested)
- Peplink InControl 2 account with API credentials and device access
- The relevant API endpoints enabled for your organization's account

## Install using HACS (custom repository)

1. Open HACS → three-dot menu → **Custom repositories**.
2. Add `https://github.com/c-a-r-s-t-e-n/peplink-incontrol2-homeassistant`
   with category **Integration**.
3. Install **Peplink InControl 2 Monitor**, restart Home Assistant.
4. Settings → Devices & Services → Add Integration → Peplink InControl 2.
5. Enter **your own** InControl 2 Client ID and Client Secret.

New versions are distributed through GitHub Releases and can be picked up by
HACS. Installing a release update may require restarting Home Assistant.

## Local installation

Copy `custom_components/peplink_incontrol2` into the HA configuration folder
under `custom_components/`, then restart and add the integration through the UI.

## Create an InControl 2 client

Sign into [InControl 2](https://incontrol2.peplink.com/), open **Client
Applications**, create an enabled client with **Bearer** token type, then copy
its Client ID and Client Secret privately into the HA config flow. The OAuth2
client-credentials flow does not need a redirect URI.

## Privacy and security

- Never open a public issue containing Client IDs, secrets, access tokens,
  serial numbers, device IPs, organization IDs or GPS coordinates.
- Credentials belong in HA's private config entry storage, not in this repo.
- The integration is read-only; no remote device controls are included.
- GPS may be sensitive: use restrictive Home Assistant access controls.

## Development

`python -m compileall -q custom_components`

Pull requests run HACS validation, hassfest, and syntax checks. Test data and
API examples must always be sanitized before committing.

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and
[CHANGELOG.md](CHANGELOG.md).

## License

MIT. © 2026 c-a-r-s-t-e-n and contributors.
