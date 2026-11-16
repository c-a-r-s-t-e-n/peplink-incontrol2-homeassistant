# API mapping and boundaries

Reviewed against the [official REST reference](https://incontrol2.peplink.com/api/restful_api) and [OAuth overview](https://incontrol2.peplink.com/api/ic2-api-doc) on 2026-11-17. Users supply their own client credentials; this project does not distribute shared credentials or operate a hosted OAuth service.

| Source | Integration use | Boundary |
|---|---|---|
| Organization / group / device inventory | Discovery, cloud status, clients, firmware, WAN status | No inferred status when absent |
| Device location | Coordinates, speed, altitude, source time | Current tracker requires online, non-static GPS within 30 minutes |
| Device bandwidth | Daily/monthly up/down totals | Current local period; MB as reported, not instantaneous throughput |
| Device event log | Returned entry count and latest entry | Not an all-time audit count |
| Device availability | Latest returned internet availability | Existing API-specific percentage mapping retained |
| WAN history | Returned records per WAN | Seven-day request, up to 8 WANs and 100 records per WAN; not total outage count |
| WAN quality dates / WAN quality | Latest report day, discovered report WAN IDs, signal and latency | Up to 16 WANs; `lms` is milliseconds, not inferred packet loss |
| Cellular tower scan dates / results | Newest scan by numeric `start_time`, then `start_date` | Recorded surveys only; never starts a scan |

Quality reports expose latency (`lms`) as well as cellular fields. Per-WAN sensors use the latest record containing that specific field, with its own timestamp. Aggregate cellular sensors remain for compatibility. Carrier metadata can be older than the newest signal sample.

No write operations, router reboot, configuration changes, speed tests or scans are implemented. Undocumented Starlink payloads, active measurement commands and guessed throughput/packet-loss fields are intentionally excluded. This integration is cloud monitoring, not direct live modem access.

## Request and storage limits

Resource requests are serialized, with a 100 ms minimum start interval. A 401 receives one token refresh attempt. A 429 sets a shared cooldown; further calls are blocked until its deadline. Network and JSON errors carry generic messages, not response bodies or request credentials. Redirects are disabled for credential-bearing requests. OAuth calls use a 20-second timeout; resource calls use 25 seconds. JSON response size is limited to 32 MiB.

The coordinator retains at most three latest quality samples plus the newest sample for each supported cellular field and latency per WAN. Older field-bearing samples are preserved only when useful. Only the newest tower survey is retained; the sensor exposes at most 20 cell attribute summaries. Report history is not imported into Recorder.

Reports begin after setup and are scheduled by elapsed monotonic time rather than a global poll counter. Failed optional reports may keep previous data and set report coverage to partial. Full inventory failures leave the coordinator unavailable; they do not falsely publish an empty account or offline state. Large multi-organization fleets require additional live load testing.
