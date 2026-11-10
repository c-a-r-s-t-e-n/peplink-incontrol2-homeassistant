"""Pure helpers for selecting reported cellular quality measurements.

Only real InControl 2 values are eligible. A WAN record containing just
coordinates/timestamps must never shadow a cellular record.
"""

SIGNAL_KEYS = (
    "rsrp", "rsrq", "rssi", "sinr", "band", "bearer", "carrier_name", "cid",
)


def latest_cellular_sample(by_wan, required=None):
    """Return (sample, wan_name) for the newest report containing required.

    A missing required field is never filled by guessing from a different
    field. Timestamp comparison falls back to ISO datetime when needed.
    """
    if not isinstance(by_wan, dict):
        return None, None
    candidates = []
    for wan_id, payload in by_wan.items():
        if not isinstance(payload, dict):
            continue
        samples = payload.get("stat")
        if not isinstance(samples, list):
            continue
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            if not any(sample.get(key) is not None for key in SIGNAL_KEYS):
                continue
            if required and sample.get(required) is None:
                continue
            try:
                stamp = float(sample.get("ts"))
            except (TypeError, ValueError):
                stamp = 0.0
            candidates.append(
                (stamp, str(sample.get("datetime") or ""), sample, payload.get("name") or f"WAN {wan_id}")
            )
    if not candidates:
        return None, None
    _, _, sample, name = max(candidates, key=lambda row: (row[0], row[1]))
    return sample, name
