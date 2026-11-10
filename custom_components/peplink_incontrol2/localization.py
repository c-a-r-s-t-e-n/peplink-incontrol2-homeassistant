"""Localizable display values for Peplink cloud diagnostics.

Values here are labels for Home Assistant frontend users, not returned to API.
"""

DIAGNOSTIC = {
    "survey_report": {"en": "Survey report available", "de": "Scanbericht vorhanden"},
    "survey_empty": {"en": "No site survey recorded", "de": "Kein Site Survey vorhanden"},
    "survey_missing": {"en": "No site survey report available", "de": "Kein Scanbericht verfügbar"},
    "wan_missing": {"en": "No WAN quality report", "de": "Kein WAN-Qualitätsbericht"},
    "wan_empty": {"en": "No WAN quality samples", "de": "Keine WAN-Messwerte"},
    "wan_no_signal": {"en": "No cellular measurements in samples", "de": "Keine Mobilfunkwerte in Messreihen"},
    "wan_ok": {"en": "Cellular measurements available", "de": "Mobilfunkwerte vorhanden"},
}


def diagnostic_label(key, language="en"):
    """Translate only our own stable diagnostic meanings."""
    values = DIAGNOSTIC.get(key, {})
    return values.get(str(language).split("-")[0], values.get("en", key))
