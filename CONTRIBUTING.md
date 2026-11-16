# Contributing

Issues and pull requests are welcome. Please include the Home Assistant version,
integration version, sanitized logs, expected/actual behavior, and reproducible
steps. Do not disclose secrets, GPS coordinates, serial numbers, client IDs,
router public IPs, or raw API output.

For code changes, create a Python 3.13 environment and run:

```sh
pip install -r requirements-dev.txt
ruff check .
ruff format --check .
pytest -q
```

CI also tests current Home Assistant with Python 3.14 and validates the integration
with hassfest and HACS. Keep existing entity unique IDs stable. Cover failures,
missing data and rate limits with synthetic fixtures; never commit tenant dumps.
Use documented fields and record the mapping and limits in `docs/API.md`.

Release tags must match the manifest version. The tag workflow tests the code and
packages only the integration directory, including branding. Publish a stable
release only after branch validation passes.
