# Community branding

The original router and dual-link emblem follows the shared community identity used by Action1 Monitor and Testo Smart Connect: navy #10283D, turquoise #32D6C5, orange #FF782D, clear typography and a consistent Home Assistant community signature. It is not Peplink's corporate logo.

Assets include 256/512 px icons, light/dark 1000/2000 px wordmarks, and a 1600 × 480 README banner. They are bundled inside the integration's `brand/` directory for Home Assistant. The README uses an absolute raw image URL so its banner also works in Marketplace.

Regenerate with `pip install Pillow` and `python scripts/build_branding.py` on a system with DejaVu Sans. Pillow is a development dependency only. Artwork is covered by the repository's MIT license. Pre-installation catalogue/CDN discovery remains controlled by Home Assistant/Marketplace, not by this repository.
