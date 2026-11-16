"""Pure helpers for selecting reported cellular quality measurements.

Only real InControl 2 values are eligible. A WAN record containing just
coordinates/timestamps must never shadow a cellular record.
"""

SIGNAL_KEYS = (
    "rsrp",
    "rsrq",
    "rssi",
    "sinr",
    "band",
    "bearer",
    "carrier_name",
    "cid",
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


def sample_key(row):
    """Compare numeric timestamps numerically, with a stable datetime fallback."""
    try:
        stamp = float(row.get("ts") or row.get("start_time") or 0)
    except (TypeError, ValueError):
        stamp = 0.0
    return stamp, str(row.get("datetime") or row.get("start_date") or "")


def latest_survey(report):
    """Find the newest survey irrespective of API ordering; empty is not zero."""
    rows = report.get("id") if isinstance(report, dict) else report
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        return None
    return max((r for r in rows if isinstance(r, dict)), key=sample_key, default=None)


def retain_samples(rows):
    """Linear scan with a bounded heap; retain recent and each field's latest values."""
    from heapq import nlargest

    samples = [row for row in rows if isinstance(row, dict)]
    recent = nlargest(3, samples, key=sample_key)
    for field in (*SIGNAL_KEYS, "lms"):
        newest = max((row for row in samples if row.get(field) is not None), key=sample_key, default=None)
        if newest is not None and newest not in recent:
            recent.append(newest)
    return sorted(recent, key=sample_key)
